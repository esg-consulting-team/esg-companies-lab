"""
DB하이텍 sustainability 보고서 하이브리드 파싱 스크립트
=========================================================

배경:
- pdfplumber는 이 문서에서 92페이지 중 87페이지(95%) 텍스트 추출 실패
- PyMuPDF 기본 추출(OCR 없음)은 표/헤더는 잡지만 본문 문단은 여전히 53% 페이지에서 실패
  (본문이 폰트가 아니라 벡터 윤곽선(curve)으로 변환되어 있어서 텍스트 레이어 자체가 없음)
- 표 내부 숫자 데이터도 같은 이유로 비어있음 확인됨 (pdfplumber/PyMuPDF 둘 다 셀 내용 공백)
  -> 헤더/제목류만 진짜 텍스트이고 본문·표 데이터 대부분은 사실상 "이미지"로 취급해야 함
- Tesseract 기반 OCR(PyMuPDF+Tesseract, unstructured ocr_only)은 인포그래픽 배경/아이콘 때문에
  한국어 인식 품질이 낮음 (실측: "ESG SSE", "0ㅁ8하이텍" 등 글자 깨짐)
- LlamaParse(Vision-LLM 기반)가 원리적으로 더 유리할 것으로 판단됨 → 이 스크립트로 실측 검증

전략 (비용 절감):
1. 먼저 PyMuPDF/pdfplumber로 각 페이지 텍스트+표 추출 시도
2. 추출된 본문 텍스트가 임계값(기본 80자) 이상 "이고" 표가 있다면 표 셀도 채워져 있으면
   → 그대로 사용 (LlamaParse 호출 안 함, 무료)
3. 본문이 부족하거나 표 셀이 비어있으면 → 해당 페이지만 모아서 LlamaParse로 전송 (유료, 필요한 페이지만)
4. 결과를 병합하여 기존 파이프라인과 동일한 JSONL 스키마로 저장

잡음 제거 (v2 추가):
- LlamaParse가 사이드바 탭 라벨("ESG Performance", "Company Profile" 등)이나 러닝헤더
  (보고서 제목), 페이지번호를 본문과 이어붙여서 추출하는 경우가 있음
  (예: "-47-ESG Performance 2024-2025 DB하이텍ESG경영보고서Company ProfileES")
  → strip_boilerplate()로 제거. 단, 표(content_type="table")는 마크다운 파이프(|)가
  구조상 정상 문자라서 절대 필터링하면 안 됨 — text 타입에만 적용.
- 필터링 후 남은 텍스트가 20자 미만이면 순수 잡음으로 보고 청크 자체를 버림

사용법:
    export LLAMA_CLOUD_API_KEY="llx-..."   # https://cloud.llamaindex.ai 에서 발급 (무료 티어: 1일 1만 크레딧)
    pip install llama-parse llama-index-core pymupdf --break-system-packages
    python3 hybrid_parse.py <PDF경로> <company_code> <year> <doc_type>

    예시:
    python3 hybrid_parse.py raw_pdf/000990_2024_sustainability.pdf 000990 2024 sustainability_report
"""

from __future__ import annotations  # Python 3.8 호환: list[int] 같은 최신 타입 문법 사용 가능하게 함

import sys
import os
import re
import json
import hashlib
import asyncio
from datetime import datetime, timezone
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit("PyMuPDF 미설치: pip install pymupdf --break-system-packages")

try:
    import pdfplumber
except ImportError:
    sys.exit("pdfplumber 미설치: pip install pdfplumber --break-system-packages")

# ---------------------------------------------------------------------------
# 설정
# ---------------------------------------------------------------------------
TEXT_THRESHOLD = 80          # 이 글자 수 미만이면 "텍스트 추출 실패"로 간주하고 LlamaParse로 보냄
LLAMAPARSE_MODE = "agentic"  # LlamaParse 파싱 모드: "fast" | "cost_effective" | "agentic" | "agentic_plus"
                              # agentic 이상부터 Vision-LLM(GPT-4.1/Gemini) 사용, 인포그래픽 문서엔 agentic 권장
LLAMAPARSE_LANG = "ko"

# --- 잡음 제거 설정 ---
MIN_CONTENT_LENGTH = 20      # 필터링 후 이 글자 수 미만이면 청크 자체를 버림 (순수 잡음으로 판단)
REPORT_TITLE_PATTERN = re.compile(r"\d{4}\s*-\s*\d{4}\s*DB\s*하이텍\s*ESG\s*경영\s*보고서")
PAGE_NUMBER_PATTERN = re.compile(r"-\s*\d{1,4}\s*-")
SIDEBAR_LABELS = [
    # DB하이텍 sustainability 보고서의 사이드바 탭 라벨 (본문에 이어붙어 추출되는 잡음)
    "Company Profile", "2023 At a Glance", "2024 At a Glance", "2025 At a Glance",
    "Sustainability", "ESG Performance", "Appendix",
]

OUT_DIR = Path(__file__).parent / "parsed_hybrid"
OUT_DIR.mkdir(exist_ok=True)


def pymupdf_pass(pdf_path: Path):
    """1차 시도: PyMuPDF로 페이지별 텍스트 + 표(간이) 추출.
    반환: {page_no(1-indexed): {"text": str, "n_chars": int}}
    """
    doc = fitz.open(pdf_path)
    results = {}
    for i, page in enumerate(doc):
        text = page.get_text().strip()
        results[i + 1] = {"text": text, "n_chars": len(text)}
    doc.close()
    return results


def pick_low_text_pages(pymupdf_results, threshold=TEXT_THRESHOLD):
    """텍스트가 부족한 페이지 번호 리스트 반환 (1-indexed)"""
    return [p for p, v in pymupdf_results.items() if v["n_chars"] < threshold]


def table_cell_fill_ratio(raw_table):
    """표의 셀 중 비어있지 않은 비율 (0~1). 낮으면 '구조는 잡혔지만 내용이 빈' 상태."""
    cells = [c for row in raw_table for c in row]
    if not cells:
        return 1.0
    filled = sum(1 for c in cells if c and str(c).strip())
    return filled / len(cells)





def make_subset_pdf(src_path: Path, page_numbers: list[int], out_path: Path):
    """지정된 페이지만 뽑아 새 PDF 생성 (LlamaParse에 필요한 페이지만 보내 비용 절감)"""
    src = fitz.open(src_path)
    sub = fitz.open()
    # page_numbers는 1-indexed
    for p in sorted(page_numbers):
        sub.insert_pdf(src, from_page=p - 1, to_page=p - 1)
    sub.save(out_path)
    sub.close()
    src.close()


async def llamaparse_pass(subset_pdf_path: Path):
    """2차 시도: LlamaParse로 부족한 페이지들만 파싱.
    llama-parse 패키지는 버전에 따라 API가 다름 (aparse / aload_data / get_json_result 등).
    설치된 버전에서 사용 가능한 메서드를 순서대로 시도해서 호환성 확보.
    반환: 페이지 순서대로 markdown 텍스트 리스트 (subset_pdf 내 순서 == 원본에서 뽑은 순서)
    """
    try:
        from llama_parse import LlamaParse
    except ImportError:
        sys.exit(
            "llama-parse 미설치: pip install llama-parse llama-index-core"
        )

    api_key = os.environ.get("LLAMA_CLOUD_API_KEY")
    if not api_key:
        sys.exit(
            "환경변수 LLAMA_CLOUD_API_KEY가 설정되어 있지 않습니다.\n"
            "https://cloud.llamaindex.ai 에서 API 키를 발급받아 설정하세요.\n"
            "  set LLAMA_CLOUD_API_KEY=llx-..."
        )

    parser = LlamaParse(
        api_key=api_key,
        result_type="markdown",
        parse_mode=LLAMAPARSE_MODE,   # 인포그래픽/벡터윤곽선 텍스트는 agentic 이상 권장
        language=LLAMAPARSE_LANG,
        verbose=True,
    )

    print(f"[LlamaParse] {subset_pdf_path.name} 전송 중 (mode={LLAMAPARSE_MODE})...")

    # --- 방법 1: 최신 v2 API (aparse + get_markdown_documents) ---
    if hasattr(parser, "aparse"):
        try:
            result = await parser.aparse(str(subset_pdf_path))
            md_documents = result.get_markdown_documents(split_by_page=True)
            return [d.text for d in md_documents]
        except Exception as e:
            print(f"  [경고] aparse 방식 실패, 다른 방식 시도: {e}")

    # --- 방법 2: get_json_result / aget_json (페이지별 md 명시적으로 담겨있음, 여러 버전에서 안정적) ---
    for method_name in ("aget_json", "get_json_result"):
        if hasattr(parser, method_name):
            try:
                method = getattr(parser, method_name)
                if asyncio.iscoroutinefunction(method):
                    json_result = await method(str(subset_pdf_path))
                else:
                    json_result = method(str(subset_pdf_path))
                # 버전에 따라 반환이 list[dict] (파일별 1개씩) 이거나 dict 하나일 수 있어 둘 다 처리
                if isinstance(json_result, list):
                    pages = json_result[0]["pages"]
                else:
                    pages = json_result["pages"]
                # 페이지 번호(page) 기준 정렬 보장 (순서가 보장 안 될 수 있어서)
                pages_sorted = sorted(pages, key=lambda p: p.get("page", 0))
                return [p.get("md") or p.get("text") or "" for p in pages_sorted]
            except Exception as e:
                print(f"  [경고] {method_name} 방식 실패, 다른 방식 시도: {e}")

    # --- 방법 3: 구버전 표준 API (load_data / aload_data) ---
    for method_name in ("aload_data", "load_data"):
        if hasattr(parser, method_name):
            try:
                method = getattr(parser, method_name)
                if asyncio.iscoroutinefunction(method):
                    documents = await method(str(subset_pdf_path))
                else:
                    documents = method(str(subset_pdf_path))
                # split_by_page=True로 생성했다면 Document가 페이지 수만큼 옴
                # 아니라면 문서 1개에 페이지 구분자(\n---\n)로 합쳐져 있을 수 있음
                if len(documents) > 1:
                    return [d.text for d in documents]
                else:
                    # 페이지 구분자로 분리 시도
                    full_text = documents[0].text
                    pages = full_text.split("\n---\n")
                    return pages
            except Exception as e:
                print(f"  [경고] {method_name} 방식 실패: {e}")

    # 모든 방법 실패 -> 사용 가능한 메서드 목록을 보여주고 종료 (디버깅용)
    available = [m for m in dir(parser) if not m.startswith("_")]
    sys.exit(
        "LlamaParse 파싱에 사용할 수 있는 메서드를 찾지 못했습니다.\n"
        f"설치된 버전에서 사용 가능한 속성/메서드: {available}\n"
        "이 목록을 보고 스크립트의 llamaparse_pass 함수를 조정해야 합니다."
    )


def table_to_markdown(table):
    if not table:
        return ""
    def clean(row):
        return [str(c).replace("\n", " ").strip() if c is not None else "" for c in row]
    header = clean(table[0])
    md = ["| " + " | ".join(header) + " |", "| " + " | ".join(["---"] * len(header)) + " |"]
    for row in table[1:]:
        row = clean(row)
        if len(row) < len(header):
            row += [""] * (len(header) - len(row))
        md.append("| " + " | ".join(row[: len(header)]) + " |")
    return "\n".join(md)


def extract_tables_and_check_empty(pdf_path: Path, fill_threshold=0.3):
    """표를 pdfplumber로 한 번만 추출하면서, 동시에 내용이 비어있는 표가 있는 페이지도 함께 판단.
    (표 추출 + 빈 표 판단을 pdfplumber 1회 순회로 합쳐 속도 개선)
    반환: (tables_by_page, empty_table_pages)
    """
    tables_by_page = {}
    empty_table_pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            try:
                raw_tables = page.extract_tables()
            except Exception:
                raw_tables = []
            page_tables = []
            ratios = []
            for raw in raw_tables:
                if raw and len(raw) >= 2:
                    page_tables.append({"markdown": table_to_markdown(raw), "raw": raw})
                    ratios.append(table_cell_fill_ratio(raw))
            tables_by_page[i + 1] = page_tables
            if ratios and min(ratios) < fill_threshold:
                empty_table_pages.append(i + 1)
    return tables_by_page, empty_table_pages


def strip_boilerplate(text: str) -> str:
    """LlamaParse가 사이드바 탭 라벨/러닝헤더(보고서 제목)/페이지번호를 본문과 이어붙여서
    추출하는 경우가 있어(예: '-47-ESG Performance 2024-2025 DB하이텍ESG경영보고서Company ProfileES'),
    이런 반복 잡음을 제거해서 검색에 실제 도움이 되는 본문 신호만 남긴다.
    주의: 표(markdown)는 절대 이 함수에 넣지 말 것 — 파이프(|)를 구조 문자로 씀.
    필터링 후 남은 글자 수가 MIN_CONTENT_LENGTH 미만이면 순수 잡음으로 보고 빈 문자열 반환.
    """
    cleaned = text
    cleaned = REPORT_TITLE_PATTERN.sub(" ", cleaned)
    for label in SIDEBAR_LABELS:
        cleaned = cleaned.replace(label, " ")
    cleaned = PAGE_NUMBER_PATTERN.sub(" ", cleaned)
    cleaned = re.sub(r"\*\*\s*\*\*", " ", cleaned)        # 빈 굵게(** **) 제거
    cleaned = re.sub(r"(?m)^\s*#+\s*$", "", cleaned)       # 내용 없는 헤딩 줄
    cleaned = re.sub(r"\s\|\s", " ", cleaned)              # 문장 중간에 낀 파이프
    cleaned = re.sub(r"(?m)^\s*\|+\s*$", "", cleaned)      # 파이프만 있는 줄
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n\s*\n+", "\n\n", cleaned)
    cleaned = cleaned.strip()
    if len(cleaned) < MIN_CONTENT_LENGTH:
        return ""
    return cleaned


def chunk_text(text, chunk_size=700, overlap=100):
    """간단 슬라이딩 윈도우 청킹 (기존 파이프라인과 동일 크기 정책)"""
    if not text.strip():
        return []
    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + chunk_size, n)
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end == n:
            break
        start = end - overlap
    return chunks


def attach_metadata(chunks, company_code, company_name, year, doc_type):
    doc_id = f"{company_code}_{year}_{doc_type}"
    out = []
    for idx, c in enumerate(chunks):
        chunk_id = f"{doc_id}_{idx:04d}"
        out.append({
            "chunk_id": chunk_id,
            "doc_id": doc_id,
            "company_code": company_code,
            "company_name": company_name,
            "year": year,
            "doc_type": doc_type,
            "page": c["page"],
            "section_title": None,
            "content_type": c["content_type"],
            "content": c["content"],
            "table_data": c.get("table_data"),
            "esg_area": None,
            "applicable_item_codes": [],
            "chunk_char_count": len(c["content"]),
            "embedding_model": "bge-m3",
            "source": c.get("source", "pymupdf"),  # 어느 경로로 추출됐는지 추적 (품질 검증용)
            "indexed_at": datetime.now(timezone.utc).isoformat(),
            "source_file_hash": hashlib.md5(c["content"].encode()).hexdigest()[:8],
        })
    return out


async def main(pdf_path_str, company_code, company_name, year, doc_type):
    pdf_path = Path(pdf_path_str)
    year = int(year)

    print(f"=== {pdf_path.name} 하이브리드 파싱 시작 ===\n")

    # 1) PyMuPDF 1차 시도 (본문 텍스트)
    print("[1/4] PyMuPDF 텍스트 추출 (1차 시도)...")
    pm_results = pymupdf_pass(pdf_path)
    low_text_pages = set(pick_low_text_pages(pm_results))
    print(f"  전체 {len(pm_results)}페이지 중 본문 텍스트 부족 페이지: {len(low_text_pages)}개\n")

    # 2) 표 추출 (pdfplumber) + 표 내용이 비어있는 페이지 확인 (1회 순회로 동시 처리)
    print("[2/4] 표 추출 (pdfplumber) 및 빈 표 페이지 확인...")
    tables_by_page, empty_table_list = extract_tables_and_check_empty(pdf_path)
    n_tables = sum(len(v) for v in tables_by_page.values())
    empty_table_pages = set(empty_table_list)
    print(f"  총 표 개수: {n_tables}, 내용 비어있는 표가 있는 페이지: {len(empty_table_pages)}개\n")

    # 본문 부족 OR 표 내용 비어있음 -> LlamaParse 재처리 대상
    low_pages = sorted(low_text_pages | empty_table_pages)
    print(f"  => LlamaParse 재처리 대상 페이지 총 {len(low_pages)}개")
    print(f"     {low_pages[:20]}{'...' if len(low_pages) > 20 else ''}\n")

    # 3) 부족 페이지만 LlamaParse로 재처리
    llamaparse_text_by_page = {}
    if low_pages:
        print(f"[3/4] LlamaParse로 {len(low_pages)}개 페이지 재처리 (비용 발생 구간)...")
        subset_path = OUT_DIR / f"_subset_{pdf_path.stem}.pdf"
        make_subset_pdf(pdf_path, low_pages, subset_path)
        md_pages = await llamaparse_pass(subset_path)
        for orig_page, md_text in zip(sorted(low_pages), md_pages):
            llamaparse_text_by_page[orig_page] = md_text
        print(f"  LlamaParse 처리 완료: {len(llamaparse_text_by_page)}페이지\n")
    else:
        print("[3/4] 텍스트 부족 페이지 없음 -> LlamaParse 호출 생략\n")

    # 4) 병합 + 청킹 + 메타데이터
    print("[4/4] 병합 및 청킹...")
    raw_chunks = []
    for page_no in sorted(pm_results.keys()):
        was_reprocessed = page_no in llamaparse_text_by_page
        if was_reprocessed:
            body_text = llamaparse_text_by_page[page_no]
            source = "llamaparse"
        else:
            body_text = pm_results[page_no]["text"]
            source = "pymupdf"

        for piece in chunk_text(body_text):
            cleaned_piece = strip_boilerplate(piece)   # 표가 아닌 본문 텍스트에만 적용
            if not cleaned_piece:
                continue  # 잡음만 남은 청크는 버림
            raw_chunks.append({
                "content": cleaned_piece,
                "content_type": "text",
                "page": page_no,
                "source": source,
            })

        # LlamaParse로 재처리된 페이지는 표 내용도 그 markdown 안에 포함되므로
        # pdfplumber가 뽑은 빈 표는 중복/공백 데이터라 건너뜀
        if not was_reprocessed:
            for t in tables_by_page.get(page_no, []):
                raw_chunks.append({
                    "content": t["markdown"],
                    "content_type": "table",
                    "page": page_no,
                    "table_data": t["raw"],
                    "source": "pdfplumber_table",
                })

    chunks = attach_metadata(raw_chunks, company_code, company_name, year, doc_type)

    out_path = OUT_DIR / f"{company_code}_{year}_{doc_type}.jsonl"
    with open(out_path, "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    n_llamaparse_chunks = sum(1 for c in chunks if c["source"] == "llamaparse")
    n_pymupdf_chunks = sum(1 for c in chunks if c["source"] == "pymupdf")
    n_table_chunks = sum(1 for c in chunks if c["source"] == "pdfplumber_table")

    print(f"\n=== 완료 ===")
    print(f"총 청크: {len(chunks)}개")
    print(f"  - PyMuPDF 직접 추출: {n_pymupdf_chunks}개")
    print(f"  - LlamaParse 재처리: {n_llamaparse_chunks}개")
    print(f"  - 표: {n_table_chunks}개")
    print(f"저장 위치: {out_path}")


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print(__doc__)
        sys.exit(1)
    pdf_path, company_code, year, doc_type = sys.argv[1:5]
    # company_name은 DB하이텍 고정 (필요시 인자 추가)
    asyncio.run(main(pdf_path, company_code, "DB하이텍", year, doc_type))
