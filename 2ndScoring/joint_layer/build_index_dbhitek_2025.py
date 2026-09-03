"""
DB하이텍(000990) 2025년도 3종 보고서 RAG 인덱스 구축 — 로컬 실행판
=====================================================================
팀원이 만든 build_rag_index.py(Google Colab용, v3)를 기반으로,
로컬(esg-workspace) 환경에서 DB하이텍 2025년 1개사만 먼저 검증하기 위해 축소.

★ 팀원 스크립트에서 그대로 가져온 부분 (하이퍼파라미터/로직 변경 없음):
  - CONFIG의 확정 값들 (임베딩 모델 gemini-embedding-001, 청크 800/100토큰,
    BM25=Kiwi, hybrid_weights 0.5/0.5 임시값)
  - clean_cell / chunk_table / extract_page_content (표-텍스트 분리, 표 토큰 분할)
  - detect_section_title / SECTION_KEYWORDS (사업·지배구조보고서 섹션 탐지)
  - process_document() (사업보고서·지배구조보고서 처리에 그대로 사용)
  - base_metadata() 스키마
  - FilteredHybridRetriever (BM25를 필터된 부분집합에서만 구축하는 방식)
  - Cell 9 동작 확인 테스트 패턴

★ 이번 로컬/파일럿 실행을 위해 바꾼 부분:
  1. Drive mount, manifest 자동 스캔(Cell 4b/4c) 제거
     → 로컬 폴더의 3개 파일(business/governance/sustainability)을 직접 지정
  2. sustainability_report는 process_document() 대신
     hybrid_parse.py 결과(parsed_hybrid/*.jsonl)를 읽어 Document로 변환.
     이유: 이 문서는 본문이 폰트가 아니라 벡터 윤곽선으로 되어있어 pdfplumber로
     텍스트 추출이 거의 안 됨 (92~102페이지 중 45페이지 이상 텍스트 손실,
     실측 확인됨). process_document()를 그대로 쓰면 팀 스키마엔 맞지만
     내용이 비어버림. → LlamaParse로 재처리된 hybrid 결과를 그대로 씀.
  3. GOOGLE_API_KEY를 getpass 대신 환경변수(GOOGLE_API_KEY)로 받음 (Colab 아님)
  4. persist_dir/checkpoint_log를 로컬 경로로 지정
  5. 5개사 확장 전, DB하이텍(000990) 2025년 1개사 3종만 대상으로 범위 한정

사용법:
    set GOOGLE_API_KEY=AIza...                     # Google AI Studio에서 발급
    pip install langchain langchain-google-genai langchain-chroma langchain-community ^
        chromadb pdfplumber kiwipiepy rank_bm25 tiktoken pandas
    python build_index_dbhitek_2025.py
"""

import os
import re
import sys
import json
import hashlib
from datetime import datetime
from pathlib import Path

import pdfplumber
import tiktoken
from kiwipiepy import Kiwi
from langchain_chroma import Chroma
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

# ---------------------------------------------------------------------------
# API 키 확인 (Colab getpass 대신 환경변수)
# ---------------------------------------------------------------------------
if not os.environ.get("GOOGLE_API_KEY"):
    sys.exit(
        "환경변수 GOOGLE_API_KEY가 설정되어 있지 않습니다.\n"
        "https://aistudio.google.com/apikey 에서 발급받아 설정하세요.\n"
        "  set GOOGLE_API_KEY=AIza...   (cmd)\n"
        '  $env:GOOGLE_API_KEY = "AIza..."   (PowerShell)'
    )

# ---------------------------------------------------------------------------
# [Cell 3] 설정값 (CONFIG) — 팀 확정값 그대로, 경로만 로컬로 조정
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent

CONFIG = {
    # --- 확정 (팀원 스크립트와 동일) ---
    "embedding_model": "gemini-embedding-001",
    "chunk_size_tokens": 800,
    "chunk_overlap_tokens": 100,
    "vectorstore_backend": "chroma",
    "bm25_tokenizer": "kiwi",
    "retrieval_k": 10,

    # --- 경로: 로컬 폴더 기준 ---
    "persist_dir": str(BASE_DIR / "chroma_db"),
    "checkpoint_log": str(BASE_DIR / "checkpoint_completed.json"),
    "hybrid_sustainability_jsonl": str(BASE_DIR / "parsed_hybrid" / "000990_2025_sustainability_report.jsonl"),

    # --- TODO: 팀 평가셋 확인 후 결정 (임의 값 아님, 팀원 스크립트와 동일) ---
    "hybrid_weights": [0.5, 0.5],
    "use_reranker": False,
}

# 이번 파일럿 대상: DB하이텍(000990) 2025년 3종
TARGET_DOCS = [
    {"company_code": "000990", "company_name": "DB하이텍", "year": 2025,
     "doc_type": "business_report",
     "file_path": str(BASE_DIR / "raw_pdf" / "000990_2025_business.pdf")},
    {"company_code": "000990", "company_name": "DB하이텍", "year": 2025,
     "doc_type": "governance_report",
     "file_path": str(BASE_DIR / "raw_pdf" / "000990_2025_governance.pdf")},
    # sustainability_report는 파일 경로 대신 hybrid jsonl에서 로드 (아래 참고)
]

kiwi = Kiwi()
RRF_K = 60

try:
    _enc = tiktoken.encoding_for_model(CONFIG["embedding_model"])
except KeyError:
    _enc = tiktoken.get_encoding("cl100k_base")


def token_len(text: str) -> int:
    return len(_enc.encode(text))


def kiwi_tokenize(text: str):
    return [t.form for t in kiwi.tokenize(text)]


splitter = RecursiveCharacterTextSplitter(
    chunk_size=CONFIG["chunk_size_tokens"],
    chunk_overlap=CONFIG["chunk_overlap_tokens"],
    length_function=token_len,
    separators=["\n\n", "\n", ". ", " ", ""],
)


# ---------------------------------------------------------------------------
# [Cell 5] 표/텍스트 추출 유틸 — 팀원 스크립트 그대로
# ---------------------------------------------------------------------------
def clean_cell(cell) -> str:
    if cell is None:
        return ""
    return str(cell).replace("\n", " ").replace("|", "\\|").strip()


def chunk_table(table_data: list, max_tokens: int) -> list:
    header = [clean_cell(c) for c in table_data[0]]
    data_rows = table_data[1:]

    header_md = (
        "| " + " | ".join(header) + " |\n"
        + "|" + "|".join(["---"] * len(header)) + "|"
    )

    def render(rows):
        body = "\n".join(
            "| " + " | ".join(clean_cell(c) for c in r) + " |" for r in rows
        )
        return header_md + ("\n" + body if body else "")

    chunks = []
    current_rows = []
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


def extract_page_content(pdf_page):
    tables = pdf_page.find_tables()
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
        for (tx0, ttop, tx1, tbottom) in table_bboxes:
            if x0 >= tx0 - 1 and x1 <= tx1 + 1 and top >= ttop - 1 and bottom <= tbottom + 1:
                return False
        return True

    non_table_page = pdf_page.filter(not_in_table)
    text = non_table_page.extract_text() or ""
    return text, table_data_list


def base_metadata(company_code, company_name, year, doc_type, doc_id,
                   chunk_id, page, content_type, source_file_hash,
                   doc_indexed_at, table_rows=None, section_title=""):
    return {
        "company_code": company_code,
        "company_name": company_name,
        "year": year,
        "doc_type": doc_type,
        "doc_id": doc_id,
        "chunk_id": chunk_id,
        "page": page,
        "section_title": section_title,
        "content_type": content_type,
        "table_data": json.dumps(table_rows, ensure_ascii=False) if table_rows else "",
        "esg_area": "",
        "applicable_item_codes": json.dumps([], ensure_ascii=False),
        "embedding_model": CONFIG["embedding_model"],
        "indexed_at": doc_indexed_at,
        "source_file_hash": source_file_hash,
    }


# ---------------------------------------------------------------------------
# [Cell 5c] 섹션 제목 키워드 탐지 — 팀원 스크립트 그대로 (사업/지배구조보고서용)
# ---------------------------------------------------------------------------
SECTION_KEYWORDS = {
    "business_report": [
        "회사의 개요", "사업의 내용", "재무에 관한 사항", "이사의 경영진단",
        "회계감사인의 감사의견", "이사회 등 회사의 기관에 관한 사항",
        "주주에 관한 사항", "임원 및 직원 등에 관한 사항",
        "계열회사 등에 관한 사항", "이해관계자와의 거래내용",
    ],
    "governance_report": [
        "주주", "이사회", "감사기구", "이사 감사의 보수",
        "내부통제", "배당", "주주총회", "공시",
    ],
}


def _normalize(line: str) -> str:
    return line.replace("·", "").replace(" ", "").replace("/", "")


def detect_section_title(line: str, doc_type: str):
    keywords = SECTION_KEYWORDS.get(doc_type)
    if not keywords:
        return None
    stripped = line.strip()
    if not stripped or len(stripped) > 40:
        return None
    norm_line = _normalize(stripped)
    for kw in keywords:
        if _normalize(kw) in norm_line:
            return kw
    return None


# ---------------------------------------------------------------------------
# [Cell 6] 문서 1건(PDF 1개) 처리 → Document 리스트 — 팀원 스크립트 그대로
# (business_report / governance_report 처리에만 사용. sustainability는 아래
#  load_hybrid_sustainability_chunks()를 대신 사용)
# ---------------------------------------------------------------------------
def process_document(company_code, company_name, year, doc_type, file_path,
                      source_file_hash, doc_indexed_at):
    doc_id = f"{company_code}_{year}_{doc_type}"
    chunks = []
    counter = 0
    current_section = ""

    with pdfplumber.open(file_path) as pdf:
        for page_number, page in enumerate(pdf.pages):
            text, tables = extract_page_content(page)

            for line in text.split("\n"):
                detected = detect_section_title(line, doc_type)
                if detected:
                    current_section = detected

            for table_data in tables:
                for piece in chunk_table(table_data, CONFIG["chunk_size_tokens"]):
                    counter += 1
                    chunk_id = f"{doc_id}_{counter:04d}"
                    meta = base_metadata(
                        company_code, company_name, year, doc_type, doc_id,
                        chunk_id, page_number + 1, "table", source_file_hash,
                        doc_indexed_at, table_rows=piece["rows"],
                        section_title=current_section,
                    )
                    meta["chunk_char_count"] = len(piece["markdown"])
                    chunks.append(Document(page_content=piece["markdown"], metadata=meta))

            if not text.strip():
                continue
            for chunk_text in splitter.split_text(text):
                counter += 1
                chunk_id = f"{doc_id}_{counter:04d}"
                meta = base_metadata(
                    company_code, company_name, year, doc_type, doc_id,
                    chunk_id, page_number + 1, "text", source_file_hash,
                    doc_indexed_at, section_title=current_section,
                )
                meta["chunk_char_count"] = len(chunk_text)
                chunks.append(Document(page_content=chunk_text, metadata=meta))

    return chunks


# ---------------------------------------------------------------------------
# ★ 신규: hybrid_parse.py 결과(JSONL)를 팀 스키마 Document로 변환
#    (sustainability_report 전용 — process_document() 대신 사용)
# ---------------------------------------------------------------------------
def load_hybrid_sustainability_chunks(jsonl_path: str, company_code: str,
                                       company_name: str, year: int,
                                       doc_indexed_at: str):
    """hybrid_parse.py가 생성한 JSONL(각 줄: chunk 1개, LlamaParse+PyMuPDF 혼합
    결과)을 읽어서, 팀의 base_metadata() 스키마에 맞는 Document 리스트로 변환.
    """
    path = Path(jsonl_path)
    if not path.exists():
        sys.exit(
            f"hybrid_parse.py 결과 파일을 찾을 수 없습니다: {jsonl_path}\n"
            "먼저 hybrid_parse.py로 sustainability PDF를 파싱해서 이 경로에 저장해두세요."
        )

    doc_type = "sustainability_report"
    doc_id = f"{company_code}_{year}_{doc_type}"

    # source_file_hash: hybrid 결과의 원본 PDF를 다시 해싱 (파일 변경 감지용)
    sustainability_pdf = BASE_DIR / "raw_pdf" / f"{company_code}_{year}_sustainability.pdf"
    if sustainability_pdf.exists():
        with open(sustainability_pdf, "rb") as f:
            source_file_hash = hashlib.md5(f.read()).hexdigest()
    else:
        source_file_hash = "unknown"

    documents = []
    with open(path, encoding="utf-8") as f:
        for idx, line in enumerate(f):
            row = json.loads(line)
            content = row["content"]
            if not content.strip():
                continue
            chunk_id = f"{doc_id}_{idx:04d}"  # 팀 스키마 규칙에 맞춰 재채번
            content_type = row.get("content_type", "text")
            table_rows = row.get("table_data")  # hybrid 결과엔 표 원본이 리스트로 있음

            meta = base_metadata(
                company_code, company_name, year, doc_type, doc_id,
                chunk_id, row.get("page", 0), content_type, source_file_hash,
                doc_indexed_at, table_rows=table_rows,
                section_title="",  # sustainability는 목차 규칙 없어 팀 결정대로 빈 문자열
            )
            meta["chunk_char_count"] = len(content)
            documents.append(Document(page_content=content, metadata=meta))

    return documents


# ---------------------------------------------------------------------------
# [Cell 7] 임베딩 + 체크포인트 인덱싱 — 팀원 스크립트와 동일 로직, 대상만 축소
# ---------------------------------------------------------------------------
def main():
    print("=== DB하이텍(000990) 2025년 인덱스 구축 시작 ===\n")

    embeddings = GoogleGenerativeAIEmbeddings(model=CONFIG["embedding_model"])
    vectorstore = Chroma(
        persist_directory=CONFIG["persist_dir"],
        embedding_function=embeddings,
    )

    if os.path.exists(CONFIG["checkpoint_log"]):
        with open(CONFIG["checkpoint_log"], encoding="utf-8") as f:
            checkpoint = json.load(f)
    else:
        checkpoint = {}

    # --- business_report, governance_report: process_document() 그대로 사용 ---
    for target in TARGET_DOCS:
        doc_id = f"{target['company_code']}_{target['year']}_{target['doc_type']}"
        file_path = target["file_path"]

        if not Path(file_path).exists():
            print(f"[건너뜀] 파일 없음: {file_path}")
            continue

        with open(file_path, "rb") as f:
            current_hash = hashlib.md5(f.read()).hexdigest()

        prior = checkpoint.get(doc_id)
        if prior and prior["source_file_hash"] == current_hash:
            print(f"스킵 (변경 없음): {doc_id}")
            continue

        if prior:
            print(f"PDF 변경 감지 → 기존 청크 삭제 후 재인덱싱: {doc_id}")
            vectorstore.delete(where={"doc_id": doc_id})

        print(f"처리 중: {doc_id}")
        try:
            doc_indexed_at = datetime.now().isoformat()
            chunks = process_document(
                company_code=target["company_code"],
                company_name=target["company_name"],
                year=target["year"],
                doc_type=target["doc_type"],
                file_path=file_path,
                source_file_hash=current_hash,
                doc_indexed_at=doc_indexed_at,
            )
            if chunks:
                ids = [c.metadata["chunk_id"] for c in chunks]
                vectorstore.add_documents(chunks, ids=ids)
                print(f"  -> {len(chunks)}개 청크 적재")

            checkpoint[doc_id] = {"source_file_hash": current_hash, "indexed_at": doc_indexed_at}
            with open(CONFIG["checkpoint_log"], "w", encoding="utf-8") as f:
                json.dump(checkpoint, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"실패 (건너뜀): {doc_id} — {e}")
            continue

    # --- sustainability_report: hybrid_parse.py 결과에서 로드 ---
    sus_doc_id = "000990_2025_sustainability_report"
    hybrid_path = CONFIG["hybrid_sustainability_jsonl"]

    if Path(hybrid_path).exists():
        with open(hybrid_path, "rb") as f:
            current_hash = hashlib.md5(f.read()).hexdigest()

        prior = checkpoint.get(sus_doc_id)
        if prior and prior["source_file_hash"] == current_hash:
            print(f"스킵 (변경 없음): {sus_doc_id}")
        else:
            if prior:
                print(f"결과 변경 감지 → 기존 청크 삭제 후 재인덱싱: {sus_doc_id}")
                vectorstore.delete(where={"doc_id": sus_doc_id})

            print(f"처리 중: {sus_doc_id} (hybrid_parse.py 결과 사용)")
            try:
                doc_indexed_at = datetime.now().isoformat()
                chunks = load_hybrid_sustainability_chunks(
                    hybrid_path, "000990", "DB하이텍", 2025, doc_indexed_at,
                )
                if chunks:
                    ids = [c.metadata["chunk_id"] for c in chunks]
                    vectorstore.add_documents(chunks, ids=ids)
                    print(f"  -> {len(chunks)}개 청크 적재")

                checkpoint[sus_doc_id] = {"source_file_hash": current_hash, "indexed_at": doc_indexed_at}
                with open(CONFIG["checkpoint_log"], "w", encoding="utf-8") as f:
                    json.dump(checkpoint, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"실패: {sus_doc_id} — {e}")
    else:
        print(f"[건너뜀] hybrid_parse.py 결과 없음: {hybrid_path}")
        print("  -> hybrid_parse.py를 먼저 실행해서 이 파일을 만들어두세요.")

    print(f"\n=== 인덱싱 완료: {len(checkpoint)}건 처리됨 ===\n")

    # -----------------------------------------------------------------------
    # [Cell 8] 필터링 지원 하이브리드 리트리버 — 팀원 스크립트와 동일
    # -----------------------------------------------------------------------
    class FilteredHybridRetriever:
        def __init__(self, vectorstore, tokenize_func, k=10, weights=(0.5, 0.5)):
            self.vectorstore = vectorstore
            self.tokenize_func = tokenize_func
            self.k = k
            self.weights = weights
            self._bm25_cache = {}

        def _get_bm25_retriever(self, filter_dict):
            sig = tuple(sorted((filter_dict or {}).items()))
            if sig in self._bm25_cache:
                return self._bm25_cache[sig]

            raw = self.vectorstore.get(
                where=filter_dict if filter_dict else None,
                include=["documents", "metadatas"],
            )
            docs = [Document(page_content=d, metadata=m)
                    for d, m in zip(raw["documents"], raw["metadatas"])]
            if not docs:
                self._bm25_cache[sig] = None
                return None

            retriever = BM25Retriever.from_documents(docs, preprocess_func=self.tokenize_func)
            retriever.k = self.k
            self._bm25_cache[sig] = retriever
            return retriever

        def invoke(self, query, filter=None, top_n=None):
            top_n = top_n or self.k
            dense_docs = self.vectorstore.similarity_search(query, k=self.k, filter=filter)
            bm25_retriever = self._get_bm25_retriever(filter)
            bm25_docs = bm25_retriever.invoke(query) if bm25_retriever else []

            scores = {}
            lookup = {}
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

    hybrid_retriever = FilteredHybridRetriever(
        vectorstore=vectorstore,
        tokenize_func=kiwi_tokenize,
        k=CONFIG["retrieval_k"],
        weights=CONFIG["hybrid_weights"],
    )

    # -----------------------------------------------------------------------
    # [Cell 9] 동작 확인 — DB하이텍(000990) 필터로 테스트
    # -----------------------------------------------------------------------
    print("=== 동작 확인 테스트 ===\n")

    test_filtered = vectorstore.similarity_search(
        "사외이사 비율", k=5, filter={"company_code": "000990"},
    )
    for d in test_filtered:
        assert d.metadata["company_code"] == "000990", "필터링 실패 — 다른 회사 청크 혼입"
    print(f"Dense 필터 테스트 통과: {len(test_filtered)}건")

    hybrid_results = hybrid_retriever.invoke(
        "이사회 산하 위원회 구성 현황", filter={"company_code": "000990"},
    )
    for d in hybrid_results:
        assert d.metadata["company_code"] == "000990", "하이브리드 필터링 실패"
    print(f"하이브리드 필터 테스트 통과: {len(hybrid_results)}건")
    for r in hybrid_results[:3]:
        print(r.metadata["doc_type"], "p.", r.metadata["page"], "|", r.page_content[:80])

    print("\n=== 추가 쿼리 예시 (E/S/G 각 1개) ===\n")
    for q in ["온실가스 배출량 저감 목표", "협력사 안전보건 지원 프로그램", "이사회 독립성 확보 방안"]:
        results = hybrid_retriever.invoke(q, filter={"company_code": "000990"}, top_n=3)
        print(f"[질문] {q}")
        for r in results:
            print(f"  - {r.metadata['doc_type']} p.{r.metadata['page']}: {r.page_content[:60]}")
        print()

    return vectorstore, hybrid_retriever


if __name__ == "__main__":
    main()
