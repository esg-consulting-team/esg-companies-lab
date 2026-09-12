"""
ESG RAG 공용 레이어 (공동 인덱스 구축 파이프라인)
=====================================================================
5개 팀원 코드([Team]Gemini_RAG_Parcing_Ju.ipynb, jin_build_index_dbhitek_2025.ipynb
+ build_index_dbhitek_2025.py/hybrid_parse.py/clean_hybrid_chunks.py,
build_rag_index_v4.ipynb, RAG0to3_shared.ipynb, index_choi.ipynb)를 비교 분석해서
RAG_joint.pdf가 정의한 "공동 레이어"(파싱 → 청킹 → 메타데이터 → 임베딩 →
dense+BM25 하이브리드 인덱스) 하나로 통합한 모듈.

어느 소스에서 무엇을 가져왔는지:
  - build_rag_index_v4      : CONFIG 골격, 표/텍스트 bbox 분리(+지속가능경영보고서
                               table_settings text 전략 폴백), 섹션 제목 역행 방지 가드,
                               DART 푸터/목차 점선 제거, tenacity 재시도 배치 임베딩,
                               manifest 자동 스캔, FilteredHybridRetriever(RRF)
  - jin_build_index_dbhitek_2025
    (+hybrid_parse.py)       : 지속가능경영보고서 PyMuPDF 1차 + LlamaParse 선택적
                               재처리(벡터 윤곽선 텍스트 대응, 페이지 서브셋으로 비용 통제),
                               표 셀 충전율 기반 "구조는 있지만 내용 빈 표" 판별
  - RAG0to3_shared          : Kiwi 형태소 POS 필터링 BM25 토크나이저(조사/불용 태그 제거),
                               source_file_hash 유틸
  - index_choi / Gemini_RAG_Parcing_Ju : 재사용할 만한 완성 로직 없음(전자는 미실행,
                               후자는 표 마크다운이 청크에 반영 안 되는 버그) — 대신
                               "무엇을 하면 안 되는지"의 반례로 아래 구현에 반영함.

이 통합본에서 원본 대비 고친 부분 (RAG_joint.pdf v1 스키마 기준):
  - doc_type을 "business_report" 등 접미사 없이 스키마가 요구하는 그대로
    business/governance/sustainability 로 통일 (5개 소스 중 4개가 접미사를 붙였음).
  - content_type에 없던 "table_caption"을 표 근처 캡션 줄 탐지로 추가.
  - source_file_hash를 모든 doc_type에서 "원본 PDF 전체의 MD5"로 통일
    (hybrid_parse.py는 청크 내용 해시를 써서 변경 감지 목적에 안 맞았음).
  - indexed_at을 UTC-aware ISO로 통일 (기존 구현들은 naive/UTC가 섞여 있었음).
  - hybrid_parse.py의 SIDEBAR_LABELS/REPORT_TITLE_PATTERN이 "DB하이텍" 문서 하나에만
    하드코딩돼 있던 것을, 페이지 반복 빈도 기반 범용 보일러플레이트 제거로 교체
    (100개사 전체에 그대로 적용 가능).
  - hybrid_parse.py에서 sustainability_report만 별도 스키마(attach_metadata, 게다가
    embedding_model이 "bge-m3"로 하드코딩된 버그 있음)를 쓰던 것을, base_metadata()
    하나로 통일.
  - embedding_model을 CONFIG로 뽑아 gemini-embedding-001 / BGE-M3 중 전환 가능하게 함
    (팀 논의 결과: 기본값은 gemini-embedding-001 — jin/v4 두 파이프라인에서 이미
    재시도 로직까지 갖춰 검증됨. BGE-M3는 로컬 GPU 준비되면 전환).

미해결로 남긴 것 (5개 소스 전부 미구현이라 이번에도 스코프 밖):
  - esg_area / applicable_item_codes 태깅 — v1 스키마 자체가 "1차 인덱싱에서는
    스킵"으로 명시. 평가셋 확인 후 채점 단계에서 채울 것.
  - page는 여전히 단일 int만 지원 (다중 페이지에 걸친 표 이어붙이기는 미구현).

사용법:
    set GOOGLE_API_KEY=AIza...            # 필수 (Google AI Studio)
    set LLAMA_CLOUD_API_KEY=llx...        # 선택 (없으면 지속가능경영보고서는
                                           #   PyMuPDF 텍스트만으로 최선 노력 처리 후 경고)
    pip install pdfplumber pymupdf tiktoken kiwipiepy rank_bm25 tenacity pandas ^
        langchain langchain-core langchain-text-splitters langchain-chroma ^
        langchain-community langchain-google-genai chromadb llama-parse llama-index-core

    python rag_common_layer.py --reports-root "raw_pdf" --persist-dir "chroma_db"

    폴더 규칙: {reports_root}/회사명(기업코드)/기업코드_연도_business.pdf
                                            (business|governance|sustainability)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    import pdfplumber
except ImportError:
    sys.exit("pdfplumber 미설치: pip install pdfplumber")

try:
    import tiktoken
except ImportError:
    sys.exit("tiktoken 미설치: pip install tiktoken")

try:
    from kiwipiepy import Kiwi
except ImportError:
    sys.exit("kiwipiepy 미설치: pip install kiwipiepy")

try:
    import pandas as pd
except ImportError:
    sys.exit("pandas 미설치: pip install pandas")

try:
    from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_message
except ImportError:
    sys.exit("tenacity 미설치: pip install tenacity")

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.retrievers import BM25Retriever
from langchain_chroma import Chroma


# =============================================================================
# CONFIG — 팀 확정값. 바꾸면 전체 재인덱싱이 필요하므로 회의 없이 임의 수정 금지
# (RAG_joint.pdf "회의 안건" 1~5번 항목에 해당)
# =============================================================================
CONFIG = {
    # --- 청킹 (확정) ---
    "chunk_size_tokens": 800,
    "chunk_overlap_tokens": 100,

    # --- 임베딩: 팀 논의 결과 두 백엔드 다 지원, 기본은 검증된 gemini ---
    "embedding_backend": "gemini",          # "gemini" | "bge_m3"
    "embedding_model_gemini": "gemini-embedding-001",
    "embedding_model_bge_m3": "BAAI/bge-m3",
    "embed_batch_size": 100,
    "embed_batch_delay_sec": 1.0,
    "embed_retry_max_attempts": 6,

    # --- 벡터스토어/BM25 (확정) ---
    "vectorstore_backend": "chroma",
    "bm25_tokenizer": "kiwi",
    "bm25_keep_pos_tags": {"NNG", "NNP", "NNB", "VV", "VA", "SL", "SN", "SH"},
    "retrieval_k": 10,

    # --- 지속가능경영보고서 하이브리드 파싱 (팀 논의 결과: 포함) ---
    "llamaparse_enabled": True,
    "llamaparse_mode": "agentic",           # 인포그래픽/벡터윤곽선 문서엔 agentic 이상 권장
    "llamaparse_lang": "ko",
    "text_threshold": 80,                   # 이 글자 수 미만 페이지는 텍스트 추출 실패로 간주
    "table_fill_threshold": 0.3,            # 표 셀 충전율이 이보다 낮으면 "빈 표"로 간주

    # --- 잡음 제거 (범용화: 특정 회사 하드코딩 없음) ---
    "boilerplate_min_repeat_ratio": 0.25,   # 전체 페이지의 이 비율 이상 반복되는 줄 = 머리말/꼬리말
    "boilerplate_min_pages": 3,
    "min_content_length": 20,               # 정제 후 이 글자 수 미만이면 잡음으로 버림
    "caption_max_len": 60,

    # --- 경로 ---
    "persist_dir": "chroma_db",
    "checkpoint_log": "checkpoint_completed.json",

    # --- TODO: 팀 평가셋(골드셋) 확인 후 튜닝, 그 전까지 임의 변경 금지 ---
    "hybrid_weights": [0.5, 0.5],           # [dense, bm25]
    "use_reranker": False,
}

RRF_K = 60  # Reciprocal Rank Fusion 표준 상수 (튜닝 대상 아님)

DOC_TYPES = ("business", "governance", "sustainability")

kiwi = Kiwi()

try:
    _enc = tiktoken.get_encoding("cl100k_base")
except Exception:
    _enc = tiktoken.get_encoding("gpt2")


def token_len(text: str) -> int:
    """임베딩 모델 기준 토큰 수 근사치 (Gemini/BGE-M3 전용 tokenizer가 없어 cl100k_base로
    근사 — 실제 토큰 수는 이보다 작을 수 있음, 청크 크기 산정용 참고치)."""
    return len(_enc.encode(text))


def kiwi_tokenize(text: str) -> list[str]:
    """BM25용 한국어 토크나이저. 조사/어미 등은 버리고 명사·동사·형용사·외래어/숫자/한자만
    남긴다 (RAG0to3_shared에서 검증된 POS 필터 — 원시 형태소 전부를 쓰는 다른 구현보다
    BM25 매칭 노이즈가 적음)."""
    keep = CONFIG["bm25_keep_pos_tags"]
    return [t.form for t in kiwi.tokenize(text) if t.tag in keep]


def file_hash(path: str | Path) -> str:
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


splitter = RecursiveCharacterTextSplitter(
    chunk_size=CONFIG["chunk_size_tokens"],
    chunk_overlap=CONFIG["chunk_overlap_tokens"],
    length_function=token_len,
    separators=["\n\n", "\n", ". ", " ", ""],
)


# =============================================================================
# 표 처리 (build_rag_index_v4 / jin 파이프라인 공통 로직)
# =============================================================================
def clean_cell(cell) -> str:
    if cell is None:
        return ""
    return str(cell).replace("\n", " ").replace("|", "\\|").strip()


def table_to_markdown(rows: list[list]) -> str:
    header = [clean_cell(c) for c in rows[0]]
    md = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    for row in rows[1:]:
        cells = [clean_cell(c) for c in row]
        if len(cells) < len(header):
            cells += [""] * (len(header) - len(cells))
        md.append("| " + " | ".join(cells[: len(header)]) + " |")
    return "\n".join(md)


def table_cell_fill_ratio(raw_table: list[list]) -> float:
    """표 셀 중 비어있지 않은 비율. 낮으면 '구조는 잡혔지만 내용이 빈' 표
    (지속가능경영보고서에서 표가 벡터 윤곽선이라 텍스트 레이어가 없는 경우)."""
    cells = [c for row in raw_table for c in row]
    if not cells:
        return 1.0
    filled = sum(1 for c in cells if c and str(c).strip())
    return filled / len(cells)


def chunk_table(table_data: list[list], max_tokens: int) -> list[dict]:
    """큰 표를 토큰 기준으로 행 단위 분할, 조각마다 헤더 행 반복."""
    header = [clean_cell(c) for c in table_data[0]]
    data_rows = table_data[1:]
    header_md = "| " + " | ".join(header) + " |\n" + "|" + "|".join(["---"] * len(header)) + "|"

    def render(rows):
        body = "\n".join("| " + " | ".join(clean_cell(c) for c in r) + " |" for r in rows)
        return header_md + ("\n" + body if body else "")

    chunks, current_rows = [], []
    for row in data_rows:
        candidate = current_rows + [row]
        if token_len(render(candidate)) > max_tokens and current_rows:
            chunks.append({"markdown": render(current_rows), "rows": current_rows})
            current_rows = [row]
        else:
            current_rows = candidate
    if current_rows:
        chunks.append({"markdown": render(current_rows), "rows": current_rows})
    return chunks or [{"markdown": header_md, "rows": []}]


def extract_page_content(pdf_page, doc_type: str = "") -> tuple[str, list[list]]:
    """표 영역을 찾아 바운딩박스를 제외한 텍스트만 반환 (표-텍스트 중복 방지).
    지속가능경영보고서는 선 없는 '디자인 표'가 많아 기본(lines) 전략으로 하나도
    안 잡히면 text 전략으로 재시도한다."""
    tables = pdf_page.find_tables()
    if doc_type == "sustainability" and not tables:
        tables = pdf_page.find_tables(
            table_settings={"vertical_strategy": "text", "horizontal_strategy": "text"}
        )

    table_bboxes = [t.bbox for t in tables]
    table_data_list = []
    for t in tables:
        try:
            extracted = t.extract()
        except Exception:
            continue
        if extracted and len(extracted) >= 2:
            table_data_list.append(extracted)

    def not_in_table(obj):
        x0, top, x1, bottom = obj.get("x0"), obj.get("top"), obj.get("x1"), obj.get("bottom")
        if x0 is None:
            return True
        return not any(
            x0 >= tx0 - 1 and x1 <= tx1 + 1 and top >= ttop - 1 and bottom <= tbottom + 1
            for (tx0, ttop, tx1, tbottom) in table_bboxes
        )

    text = pdf_page.filter(not_in_table).extract_text() or ""
    return text, table_data_list


# =============================================================================
# 잡음 제거 — 범용 (특정 회사/보고서 문구에 하드코딩하지 않음)
# =============================================================================
NOISE_LINE_PATTERN = re.compile(r"^전자공시시스템\s*dart\.fss\.or\.kr\s*Page\s*\d+\s*$")
PAGE_NUMBER_PATTERN = re.compile(r"^-\s*\d{1,4}\s*-$")
TOC_DOT_PATTERN = re.compile(r"\.{10,}")
CAPTION_PATTERN = re.compile(r"^\s*(?:<\s*)?(?:표|Table|TABLE)\s*[0-9IVXⅠ-Ⅹ가-힣.\-]*\s*[.\)]?\s*\S")


def strip_noise_lines(text: str) -> str:
    """DART 뷰어 푸터/독립된 페이지번호 줄 제거 (모든 회사 공통 구조적 잡음)."""
    return "\n".join(
        ln for ln in text.split("\n")
        if not NOISE_LINE_PATTERN.match(ln.strip()) and not PAGE_NUMBER_PATTERN.match(ln.strip())
    )


def is_toc_chunk(text: str) -> bool:
    """점선 목차(.......) 덩어리 판별 (점 10개 이상 연속이 3군데 이상)."""
    return len(TOC_DOT_PATTERN.findall(text)) >= 3


def build_boilerplate_line_set(pages_text: dict[int, str]) -> set[str]:
    """여러 페이지에 걸쳐 그대로 반복되는 짧은 줄(사이드바 라벨, 러닝헤더 등)을
    빈도 기반으로 탐지. hybrid_parse.py가 'DB하이텍' 문서 하나에만 하드코딩했던
    SIDEBAR_LABELS 방식을 대체 — 100개사 전체에 그대로 적용 가능."""
    n_pages = len(pages_text)
    if n_pages < CONFIG["boilerplate_min_pages"]:
        return set()
    counter = Counter()
    for text in pages_text.values():
        for ln in {ln.strip() for ln in text.split("\n") if ln.strip()}:
            if len(ln) < 80:
                counter[ln] += 1
    threshold = max(CONFIG["boilerplate_min_pages"], int(n_pages * CONFIG["boilerplate_min_repeat_ratio"]))
    return {ln for ln, cnt in counter.items() if cnt >= threshold}


def strip_boilerplate_lines(text: str, boilerplate: set[str]) -> str:
    if not boilerplate:
        return text
    return "\n".join(ln for ln in text.split("\n") if ln.strip() not in boilerplate)


def extract_table_captions(text: str) -> tuple[str, list[str]]:
    """표 캡션으로 보이는 줄("표 3-1. ...", "<Table 2> ...")을 본문에서 분리해낸다.
    분리된 줄은 content_type=table_caption 청크로 별도 저장하고, 남은 본문에서는 제거한다."""
    kept_lines, captions = [], []
    for ln in text.split("\n"):
        stripped = ln.strip()
        if stripped and len(stripped) <= CONFIG["caption_max_len"] and CAPTION_PATTERN.match(stripped):
            captions.append(stripped)
        else:
            kept_lines.append(ln)
    return "\n".join(kept_lines), captions


# =============================================================================
# 섹션 제목 탐지 (사업/지배구조보고서 전용 — 지속가능경영보고서는 목차 규칙이
# 없어 v1 스키마 결정대로 null 유지)
# =============================================================================
SECTION_KEYWORDS = {
    "business": [
        "회사의 개요", "사업의 내용", "재무에 관한 사항", "이사의 경영진단",
        "회계감사인의 감사의견", "이사회 등 회사의 기관에 관한 사항",
        "주주에 관한 사항", "임원 및 직원 등에 관한 사항",
        "계열회사 등에 관한 사항", "이해관계자와의 거래내용",
    ],
    "governance": [
        "주주", "이사회", "감사기구", "이사 감사의 보수",
        "내부통제", "배당", "주주총회", "공시",
    ],
}


def _normalize(line: str) -> str:
    return line.replace("·", "").replace(" ", "").replace("/", "")


def detect_section_title(line: str, doc_type: str) -> Optional[tuple[str, int]]:
    """짧고 키워드를 포함한 줄을 섹션 제목 후보로 판단. 반환값의 int는
    SECTION_KEYWORDS 리스트 상 순서 인덱스 — 호출부에서 역행(오탐) 방지에 사용."""
    keywords = SECTION_KEYWORDS.get(doc_type)
    if not keywords:
        return None
    stripped = line.strip()
    if not stripped or len(stripped) > 40:
        return None
    norm_line = _normalize(stripped)
    for idx, kw in enumerate(keywords):
        if _normalize(kw) in norm_line:
            return kw, idx
    return None


# =============================================================================
# 메타데이터 (v1 스키마, 팀 공용 단일 소스)
# =============================================================================
def base_metadata(company_code, company_name, year, doc_type, doc_id, chunk_id,
                   page, content_type, source_file_hash_, doc_indexed_at,
                   table_rows=None, section_title="") -> dict:
    """Chroma 메타데이터는 str/int/float/bool만 허용 (None, list 불가)
    -> None은 빈 문자열로, list/JSON은 문자열로 직렬화."""
    return {
        "company_code": company_code,
        "company_name": company_name,
        "year": int(year),
        "doc_type": doc_type,                     # business | governance | sustainability
        "doc_id": doc_id,
        "chunk_id": chunk_id,
        "page": page,
        "section_title": section_title,
        "content_type": content_type,              # text | table | table_caption
        "table_data": json.dumps(table_rows, ensure_ascii=False) if table_rows else "",
        "esg_area": "",                             # 1차 인덱싱 스킵 (v1 스키마 결정)
        "applicable_item_codes": json.dumps([], ensure_ascii=False),
        "embedding_model": (
            CONFIG["embedding_model_gemini"] if CONFIG["embedding_backend"] == "gemini"
            else CONFIG["embedding_model_bge_m3"]
        ),
        "indexed_at": doc_indexed_at,
        "source_file_hash": source_file_hash_,
    }


def _make_chunk(counter: int, doc_id: str, content: str, **meta_kwargs) -> Document:
    counter += 1
    chunk_id = f"{doc_id}_{counter:04d}"
    meta = base_metadata(doc_id=doc_id, chunk_id=chunk_id, **meta_kwargs)
    meta["chunk_char_count"] = len(content)
    return Document(page_content=content, metadata=meta), counter


# =============================================================================
# 사업보고서 / 지배구조보고서 파싱 (pdfplumber 단독으로 충분)
# =============================================================================
def parse_business_or_governance(company_code: str, company_name: str, year: int,
                                  doc_type: str, file_path: str,
                                  source_file_hash_: str, doc_indexed_at: str) -> list[Document]:
    doc_id = f"{company_code}_{year}_{doc_type}"

    with pdfplumber.open(file_path) as pdf:
        raw_pages, tables_by_page = {}, {}
        for i, page in enumerate(pdf.pages):
            text, tables = extract_page_content(page, doc_type)
            raw_pages[i + 1] = text
            tables_by_page[i + 1] = tables

    boilerplate = build_boilerplate_line_set(raw_pages)

    chunks: list[Document] = []
    counter = 0
    current_section, current_section_idx = "", -1

    for page_number in sorted(raw_pages):
        text = strip_noise_lines(strip_boilerplate_lines(raw_pages[page_number], boilerplate))

        for line in text.split("\n"):
            detected = detect_section_title(line, doc_type)
            if detected and detected[1] >= current_section_idx:
                current_section, current_section_idx = detected

        text, captions = extract_table_captions(text)
        for caption in captions:
            doc, counter = _make_chunk(
                counter, doc_id, caption,
                company_code=company_code, company_name=company_name, year=year,
                doc_type=doc_type, page=page_number, content_type="table_caption",
                source_file_hash_=source_file_hash_, doc_indexed_at=doc_indexed_at,
                section_title=current_section,
            )
            chunks.append(doc)

        for table_data in tables_by_page[page_number]:
            for piece in chunk_table(table_data, CONFIG["chunk_size_tokens"]):
                doc, counter = _make_chunk(
                    counter, doc_id, piece["markdown"],
                    company_code=company_code, company_name=company_name, year=year,
                    doc_type=doc_type, page=page_number, content_type="table",
                    source_file_hash_=source_file_hash_, doc_indexed_at=doc_indexed_at,
                    table_rows=piece["rows"], section_title=current_section,
                )
                chunks.append(doc)

        if not text.strip():
            continue
        for piece in splitter.split_text(text):
            if is_toc_chunk(piece) or len(piece.strip()) < CONFIG["min_content_length"]:
                continue
            doc, counter = _make_chunk(
                counter, doc_id, piece,
                company_code=company_code, company_name=company_name, year=year,
                doc_type=doc_type, page=page_number, content_type="text",
                source_file_hash_=source_file_hash_, doc_indexed_at=doc_indexed_at,
                section_title=current_section,
            )
            chunks.append(doc)

    return chunks


# =============================================================================
# 지속가능경영보고서 파싱 — PyMuPDF 1차 + (필요 시) LlamaParse 재처리
# 배경: 본문이 폰트가 아니라 벡터 윤곽선(curve)으로 저장된 경우가 많아
# pdfplumber/PyMuPDF 텍스트 추출이 대량 실패함 (jin 파이프라인 실측: 92페이지 중
# 87페이지 손실). Tesseract OCR도 인포그래픽 배경 때문에 한국어 인식률이 낮아
# LlamaParse(Vision-LLM)를 텍스트 부족/빈 표 페이지에만 선택적으로 사용해 비용 통제.
# =============================================================================
def _pymupdf_pass(pdf_path: Path) -> dict[int, str]:
    try:
        import fitz  # PyMuPDF
    except ImportError:
        sys.exit("pymupdf 미설치: pip install pymupdf")
    doc = fitz.open(pdf_path)
    try:
        return {i + 1: page.get_text().strip() for i, page in enumerate(doc)}
    finally:
        doc.close()


def _make_subset_pdf(src_path: Path, page_numbers: list[int], out_path: Path) -> None:
    import fitz
    src = fitz.open(src_path)
    sub = fitz.open()
    for p in sorted(page_numbers):
        sub.insert_pdf(src, from_page=p - 1, to_page=p - 1)
    sub.save(out_path)
    sub.close()
    src.close()


async def _llamaparse_pass(subset_pdf_path: Path) -> list[str]:
    """설치된 llama-parse 버전에 따라 API가 다르므로 사용 가능한 메서드를
    순서대로 시도해 호환성을 확보한다."""
    try:
        from llama_parse import LlamaParse
    except ImportError:
        sys.exit("llama-parse 미설치: pip install llama-parse llama-index-core")

    api_key = os.environ.get("LLAMA_CLOUD_API_KEY")
    if not api_key:
        raise RuntimeError("LLAMA_CLOUD_API_KEY 미설정 — 지속가능경영보고서 부족 페이지 재처리 불가")

    parser = LlamaParse(
        api_key=api_key, result_type="markdown",
        parse_mode=CONFIG["llamaparse_mode"], language=CONFIG["llamaparse_lang"], verbose=True,
    )

    import asyncio

    if hasattr(parser, "aparse"):
        try:
            result = await parser.aparse(str(subset_pdf_path))
            return [d.text for d in result.get_markdown_documents(split_by_page=True)]
        except Exception as e:
            print(f"  [경고] aparse 방식 실패: {e}")

    for method_name in ("aget_json", "get_json_result"):
        if hasattr(parser, method_name):
            try:
                method = getattr(parser, method_name)
                json_result = await method(str(subset_pdf_path)) if asyncio.iscoroutinefunction(method) \
                    else method(str(subset_pdf_path))
                pages = json_result[0]["pages"] if isinstance(json_result, list) else json_result["pages"]
                pages_sorted = sorted(pages, key=lambda p: p.get("page", 0))
                return [p.get("md") or p.get("text") or "" for p in pages_sorted]
            except Exception as e:
                print(f"  [경고] {method_name} 방식 실패: {e}")

    for method_name in ("aload_data", "load_data"):
        if hasattr(parser, method_name):
            try:
                method = getattr(parser, method_name)
                documents = await method(str(subset_pdf_path)) if asyncio.iscoroutinefunction(method) \
                    else method(str(subset_pdf_path))
                if len(documents) > 1:
                    return [d.text for d in documents]
                return documents[0].text.split("\n---\n")
            except Exception as e:
                print(f"  [경고] {method_name} 방식 실패: {e}")

    available = [m for m in dir(parser) if not m.startswith("_")]
    raise RuntimeError(f"LlamaParse 파싱 메서드를 찾지 못함. 사용 가능한 속성: {available}")


def parse_sustainability(company_code: str, company_name: str, year: int,
                          file_path: str, source_file_hash_: str, doc_indexed_at: str,
                          out_dir: Path) -> list[Document]:
    import asyncio

    doc_type = "sustainability"
    doc_id = f"{company_code}_{year}_{doc_type}"
    pdf_path = Path(file_path)

    pm_pages = _pymupdf_pass(pdf_path)
    low_text_pages = {p for p, t in pm_pages.items() if len(t) < CONFIG["text_threshold"]}

    tables_by_page, empty_table_pages = {}, set()
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            try:
                raw_tables = page.extract_tables()
            except Exception:
                raw_tables = []
            good = [{"markdown": table_to_markdown(t), "raw": t} for t in raw_tables if t and len(t) >= 2]
            tables_by_page[i + 1] = good
            ratios = [table_cell_fill_ratio(t["raw"]) for t in good]
            if ratios and min(ratios) < CONFIG["table_fill_threshold"]:
                empty_table_pages.add(i + 1)

    low_pages = sorted(low_text_pages | empty_table_pages)
    llamaparse_text_by_page: dict[int, str] = {}

    if low_pages and CONFIG["llamaparse_enabled"] and os.environ.get("LLAMA_CLOUD_API_KEY"):
        out_dir.mkdir(exist_ok=True, parents=True)
        subset_path = out_dir / f"_subset_{pdf_path.stem}.pdf"
        _make_subset_pdf(pdf_path, low_pages, subset_path)
        try:
            md_pages = asyncio.run(_llamaparse_pass(subset_path))
            for page_no, md_text in zip(sorted(low_pages), md_pages):
                llamaparse_text_by_page[page_no] = md_text
        except Exception as e:
            print(f"  [경고] LlamaParse 재처리 실패, PyMuPDF 텍스트로 최선 노력 처리: {e}")
    elif low_pages:
        print(f"  [경고] {len(low_pages)}개 페이지 텍스트/표 부족하나 LlamaParse 비활성/키 없음 "
              f"— PyMuPDF 텍스트만으로 최선 노력 처리 (내용 손실 가능)")

    merged_pages = {
        p: (llamaparse_text_by_page[p] if p in llamaparse_text_by_page else pm_pages[p])
        for p in pm_pages
    }
    boilerplate = build_boilerplate_line_set(merged_pages)

    chunks: list[Document] = []
    counter = 0
    for page_no in sorted(merged_pages):
        was_reprocessed = page_no in llamaparse_text_by_page
        text = strip_noise_lines(strip_boilerplate_lines(merged_pages[page_no], boilerplate))
        text, captions = extract_table_captions(text)

        for caption in captions:
            doc, counter = _make_chunk(
                counter, doc_id, caption,
                company_code=company_code, company_name=company_name, year=year,
                doc_type=doc_type, page=page_no, content_type="table_caption",
                source_file_hash_=source_file_hash_, doc_indexed_at=doc_indexed_at,
            )
            chunks.append(doc)

        for piece in splitter.split_text(text):
            if is_toc_chunk(piece) or len(piece.strip()) < CONFIG["min_content_length"]:
                continue
            doc, counter = _make_chunk(
                counter, doc_id, piece,
                company_code=company_code, company_name=company_name, year=year,
                doc_type=doc_type, page=page_no, content_type="text",
                source_file_hash_=source_file_hash_, doc_indexed_at=doc_indexed_at,
            )
            chunks.append(doc)

        # LlamaParse로 재처리된 페이지는 표 내용이 그 markdown 안에 이미 포함되므로,
        # pdfplumber가 뽑은 (내용 비어있을 가능성 높은) 표는 건너뜀
        if not was_reprocessed:
            for t in tables_by_page.get(page_no, []):
                doc, counter = _make_chunk(
                    counter, doc_id, t["markdown"],
                    company_code=company_code, company_name=company_name, year=year,
                    doc_type=doc_type, page=page_no, content_type="table",
                    source_file_hash_=source_file_hash_, doc_indexed_at=doc_indexed_at,
                    table_rows=t["raw"],
                )
                chunks.append(doc)

    return chunks


PARSERS = {
    "business": parse_business_or_governance,
    "governance": parse_business_or_governance,
}


# =============================================================================
# 임베딩 백엔드 (팀 논의 결과: 설정으로 전환 가능, 기본 gemini)
# =============================================================================
def get_embeddings():
    backend = CONFIG["embedding_backend"]
    if backend == "gemini":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        if not os.environ.get("GOOGLE_API_KEY"):
            sys.exit(
                "환경변수 GOOGLE_API_KEY가 설정되어 있지 않습니다.\n"
                "https://aistudio.google.com/apikey 에서 발급받아 설정하세요."
            )
        return GoogleGenerativeAIEmbeddings(model=CONFIG["embedding_model_gemini"])

    if backend == "bge_m3":
        try:
            from FlagEmbedding import BGEM3FlagModel
        except ImportError:
            sys.exit("BGE-M3 사용 위해 FlagEmbedding 미설치: pip install FlagEmbedding")

        class BGEM3Embeddings:
            """LangChain Embeddings 인터페이스(embed_documents/embed_query)를 구현한
            BGE-M3 로컬 임베딩 어댑터. Dense 벡터만 사용 (Sparse는 팀이 이미 Kiwi+BM25로
            별도 구축하므로 중복 사용 안 함)."""

            def __init__(self, model_name: str):
                self._model = BGEM3FlagModel(model_name, use_fp16=True)

            def embed_documents(self, texts: list[str]) -> list[list[float]]:
                out = self._model.encode(texts, return_dense=True, return_sparse=False)
                return [v.tolist() for v in out["dense_vecs"]]

            def embed_query(self, text: str) -> list[float]:
                return self.embed_documents([text])[0]

        return BGEM3Embeddings(CONFIG["embedding_model_bge_m3"])

    raise ValueError(f"알 수 없는 embedding_backend: {backend}")


@retry(
    wait=wait_exponential(multiplier=2, min=5, max=90),
    stop=stop_after_attempt(CONFIG["embed_retry_max_attempts"]),
    retry=retry_if_exception_message(match=".*RESOURCE_EXHAUSTED.*|.*429.*|.*rate limit.*"),
    reraise=True,
)
def _add_batch_with_retry(vectorstore, batch_chunks: list[Document]) -> None:
    ids = [c.metadata["chunk_id"] for c in batch_chunks]
    vectorstore.add_documents(batch_chunks, ids=ids)


def add_documents_throttled(vectorstore, chunks: list[Document]) -> None:
    """청크를 배치로 나눠 넣고 배치 사이 대기 -> API 429 완화.
    배치 하나가 재시도까지 실패하면 그 배치만 실패 처리(문서 단위 실패로 전파)."""
    batch_size, delay = CONFIG["embed_batch_size"], CONFIG["embed_batch_delay_sec"]
    total = len(chunks)
    for i in range(0, total, batch_size):
        batch = chunks[i:i + batch_size]
        _add_batch_with_retry(vectorstore, batch)
        if i + batch_size < total:
            time.sleep(delay)


# =============================================================================
# Manifest 자동 스캔 — {reports_root}/회사명(기업코드)/기업코드_연도_doctype.pdf
# =============================================================================
FOLDER_PATTERN = re.compile(r"^(.*)\((\d{6})\)$")
FILE_PATTERN = re.compile(r"^(\d{6})_(\d{4})_(business|governance|sustainability)\.pdf$")


def build_manifest(reports_root: str) -> pd.DataFrame:
    root = Path(reports_root)
    if not root.exists():
        raise FileNotFoundError(f"경로를 찾을 수 없음: {reports_root}")

    rows = []
    for company_dir in sorted(root.iterdir()):
        if not company_dir.is_dir():
            continue
        m = FOLDER_PATTERN.match(company_dir.name)
        if not m:
            print(f"[건너뜀] 폴더명 규칙 불일치: {company_dir.name}")
            continue
        company_name, company_code = m.group(1), m.group(2)

        for pdf_file in sorted(company_dir.glob("*.pdf")):
            fm = FILE_PATTERN.match(pdf_file.name)
            if not fm:
                print(f"[건너뜀] 파일명 규칙 불일치: {pdf_file.name}")
                continue
            file_code, year, doc_type = fm.groups()
            if file_code != company_code:
                print(f"[경고] 폴더코드({company_code})와 파일코드({file_code}) 불일치: {pdf_file}")
                continue
            rows.append({
                "company_code": company_code, "company_name": company_name,
                "year": int(year), "doc_type": doc_type, "file_path": str(pdf_file),
            })
    return pd.DataFrame(rows)


# =============================================================================
# 체크포인트 기반 증분 인덱싱 드라이버
# =============================================================================
def build_index(manifest: pd.DataFrame, vectorstore, persist_dir: str) -> dict:
    checkpoint_path = Path(CONFIG["checkpoint_log"])
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8")) if checkpoint_path.exists() else {}
    hybrid_out_dir = Path(persist_dir).parent / "parsed_hybrid"

    for _, row in manifest.iterrows():
        doc_id = f"{row['company_code']}_{row['year']}_{row['doc_type']}"
        current_hash = file_hash(row["file_path"])

        prior = checkpoint.get(doc_id)
        if prior and prior["source_file_hash"] == current_hash:
            print(f"스킵 (변경 없음): {doc_id}")
            continue
        if prior:
            print(f"PDF 변경 감지 → 기존 청크 삭제 후 재인덱싱: {doc_id}")
            vectorstore.delete(where={"doc_id": doc_id})

        print(f"처리 중: {doc_id}")
        try:
            doc_indexed_at = datetime.now(timezone.utc).isoformat()
            if row["doc_type"] == "sustainability":
                chunks = parse_sustainability(
                    row["company_code"], row["company_name"], row["year"],
                    row["file_path"], current_hash, doc_indexed_at, hybrid_out_dir,
                )
            else:
                chunks = PARSERS[row["doc_type"]](
                    row["company_code"], row["company_name"], row["year"], row["doc_type"],
                    row["file_path"], current_hash, doc_indexed_at,
                )

            if chunks:
                add_documents_throttled(vectorstore, chunks)
                print(f"  -> {len(chunks)}개 청크 적재")

            checkpoint[doc_id] = {"source_file_hash": current_hash, "indexed_at": doc_indexed_at}
            checkpoint_path.write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"실패 (건너뜀): {doc_id} — {e}")
            continue

    print(f"\n완료: {len(checkpoint)}건 / 전체 {len(manifest)}건")
    return checkpoint


# =============================================================================
# 하이브리드 검색 (dense + BM25, RRF) — company_code 등 필터된 부분집합에서만
# BM25를 구축해 100개사 규모에서도 전체 재구축 없이 동작
# =============================================================================
class FilteredHybridRetriever:
    def __init__(self, vectorstore, tokenize_func=kiwi_tokenize, k=None, weights=None):
        self.vectorstore = vectorstore
        self.tokenize_func = tokenize_func
        self.k = k or CONFIG["retrieval_k"]
        self.weights = weights or CONFIG["hybrid_weights"]
        self._bm25_cache: dict[tuple, Optional[BM25Retriever]] = {}

    def _get_bm25_retriever(self, filter_dict) -> Optional[BM25Retriever]:
        sig = tuple(sorted((filter_dict or {}).items()))
        if sig in self._bm25_cache:
            return self._bm25_cache[sig]

        raw = self.vectorstore.get(where=filter_dict or None, include=["documents", "metadatas"])
        docs = [Document(page_content=d, metadata=m) for d, m in zip(raw["documents"], raw["metadatas"])]
        if not docs:
            self._bm25_cache[sig] = None
            return None

        retriever = BM25Retriever.from_documents(docs, preprocess_func=self.tokenize_func)
        retriever.k = self.k
        self._bm25_cache[sig] = retriever
        return retriever

    def invoke(self, query: str, filter: Optional[dict] = None, top_n: Optional[int] = None) -> list[Document]:
        top_n = top_n or self.k
        dense_docs = self.vectorstore.similarity_search(query, k=self.k, filter=filter)
        bm25_retriever = self._get_bm25_retriever(filter)
        bm25_docs = bm25_retriever.invoke(query) if bm25_retriever else []

        scores, lookup = {}, {}
        for rank, doc in enumerate(dense_docs):
            key = doc.metadata["chunk_id"]
            scores[key] = scores.get(key, 0.0) + self.weights[0] * (1.0 / (RRF_K + rank))
            lookup[key] = doc
        for rank, doc in enumerate(bm25_docs):
            key = doc.metadata["chunk_id"]
            scores[key] = scores.get(key, 0.0) + self.weights[1] * (1.0 / (RRF_K + rank))
            lookup[key] = doc

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [lookup[k] for k, _ in ranked[:top_n]]


# =============================================================================
# CLI
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description="ESG RAG 공용 레이어 — 인덱스 구축")
    parser.add_argument("--reports-root", default="raw_pdf",
                         help="회사명(코드)/코드_연도_doctype.pdf 구조의 루트 폴더")
    parser.add_argument("--persist-dir", default=CONFIG["persist_dir"])
    parser.add_argument("--embedding-backend", choices=["gemini", "bge_m3"], default=None)
    args = parser.parse_args()

    if args.embedding_backend:
        CONFIG["embedding_backend"] = args.embedding_backend
    CONFIG["persist_dir"] = args.persist_dir

    manifest = build_manifest(args.reports_root)
    if manifest.empty:
        sys.exit(f"{args.reports_root}에서 규칙에 맞는 PDF를 찾지 못했습니다.")
    print(f"Manifest: {len(manifest)}건 ({manifest['company_code'].nunique()}개사)")

    embeddings = get_embeddings()
    vectorstore = Chroma(persist_directory=CONFIG["persist_dir"], embedding_function=embeddings)

    build_index(manifest, vectorstore, CONFIG["persist_dir"])

    hybrid = FilteredHybridRetriever(vectorstore)
    first_code = manifest.iloc[0]["company_code"]
    print(f"\n=== 동작 확인 ({first_code}) ===")
    for doc in hybrid.invoke("사외이사 비율", filter={"company_code": first_code}, top_n=3):
        print(f"  [{doc.metadata['doc_type']} p.{doc.metadata['page']}] {doc.page_content[:60]}")


if __name__ == "__main__":
    main()
