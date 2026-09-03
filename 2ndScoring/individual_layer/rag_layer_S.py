"""
S(사회/Social) 개별 레이어 — 34개 채점항목 RAG 자동 채점
=====================================================================
RAG_joint.pdf의 정의: "공동작업 = 인덱스가 만들어지기 전까지의 모든 것 / 개인작업 = 그
인덱스를 갖고 각자 파트(E/S/G+공시+반도체)의 91문항을 검색·추출하는 로직(쿼리 설계,
프롬프트, 채점 함수, 결과 검증)". 이 파일은 그 "개인작업" 중 S(사회) 파트 담당.

전제(build_rag_index_v6_production.ipynb 확인 결과):
  - v6는 순수 인덱싱 파이프라인이고, 채점 체인은 어디에도 없음 (esg_area/
    applicable_item_codes도 빈 값) → 아래는 전부 신규 구현.
  - v6가 실제로 만든 Chroma 인덱스의 doc_type은 접미사 있는 값
    (business_report/governance_report/sustainability_report) — 이 파일도
    반드시 그 값을 그대로 써야 실제 인덱스와 필터가 맞음. (참고: 저장소에 있는
    rag_common_layer.py는 접미사 없는 스키마를 쓰는 별개 실험 스크립트이므로 그 쪽
    스키마를 섞으면 필터가 조용히 0건을 반환함 — 절대 혼용하지 말 것.)
  - v6 인덱스는 아직 완주되지 않음(마지막 확인 시 100개사 중 27개사만 반영, Colab에서
    중단됨) → 이 스크립트는 "그 시점까지 인덱싱된 회사"에 대해서만 동작하고, 인덱스에
    없는 회사는 자동으로 건너뛰며 경고를 남김.
  - v6에 "평가 대상(74개사) vs 컨설팅 대상" 구분이 전혀 없음 → 이 스크립트도 회사 목록을
    받지 않으면 인덱스에 실제로 존재하는 회사 전체(discover_indexed_companies)를 대상으로
    돈다. 74개사로 제한하려면 --company-list로 별도 목록을 넘길 것.

데이터 소스: Docs/채점기준표/ESG_핵심지표_채점기준표_S(사회).xlsx
  01_ESG통합진단마스터 시트의 34개 S-* 항목(분류코드/항목설명/채점유형/최대단계수/
  배점구조 요약/점검기준 상세/실사진단질문)을 실행 시점에 직접 읽는다 — 팀원이 이
  워크북 값을 갱신해도 코드 수정 없이 반영되도록, 항목 텍스트를 파이썬에 하드코딩하지
  않음.

채점 방식 (34개 항목 전수 확인 결과 4가지 유형으로 수렴):
  - 단계형/선택형: "N단계(또는 N개 요건) 중 증거가 뒷받침하는 가장 높은 단계"를 LLM이
    고르고, 그 단계를 0~100 등간 배점표(level_to_score)로 환산 — 산술은 파이썬이 함.
  - 복합가중형: 항목설명(O열)에 이미 하위요소별 배점이 명시돼 있어("요건1=20점" 등),
    LLM이 하위요소마다 만점 대비 실제 배점(가중치 반영 완료된 값)을 매기게 하고,
    파이썬은 그 값을 합산·clamp만 함.
  - 감점형: 100점에서 위반유형별(-50/-30/-10) 차감, 위반이 없으면 100점. LLM은 위반
    사실만 찾고, 차감 계산은 파이썬이 함.
  공통 원칙: "사실 판단(단계/위반/하위요소 충족 여부)은 LLM, 최종 산술은 파이썬" —
  LLM이 최종 점수를 직접 산출하게 하지 않음 (연산 오류 리스크 축소).

결과 검증(RAG_joint.pdf "채점 함수, 결과 검증"에 해당):
  - LLM이 스스로 매기는 confidence(high/medium/low)와 insufficient_data 플래그,
  - 근거 청크가 0건이면 무조건, confidence=low거나 insufficient_data=True면 무조건,
  - need_review=True로 플래그 후 결과 CSV에 남김 (WBS 2-4-4 "Human-in-the-loop
    이상치 검수" 단계에서 사람이 우선적으로 볼 행).

사용법:
    set GOOGLE_API_KEY=AIza...
    pip install langchain-google-genai langchain-chroma langchain-community ^
        langchain-core chromadb kiwipiepy rank_bm25 openpyxl pandas tenacity

    # v6 인덱스가 로컬에 이미 있는 경우 (Colab이면 Drive 마운트 후 동일 인자로):
    python rag_layer_S.py --persist-dir "chroma_db" --output-csv "S_채점결과.csv"

    # 특정 회사만:
    python rag_layer_S.py --persist-dir "chroma_db" --company-code 000990
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

try:
    import pandas as pd
except ImportError:
    sys.exit("pandas 미설치: pip install pandas")

try:
    import openpyxl
except ImportError:
    sys.exit("openpyxl 미설치: pip install openpyxl")

try:
    from kiwipiepy import Kiwi
except ImportError:
    sys.exit("kiwipiepy 미설치: pip install kiwipiepy")

try:
    from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_message
except ImportError:
    sys.exit("tenacity 미설치: pip install tenacity")

from pydantic import BaseModel, Field
from langchain_core.documents import Document
from langchain_community.retrievers import BM25Retriever
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI


# =============================================================================
# CONFIG — v6와 동일 스키마 값(임베딩 모델/persist 규칙)에 채점 전용 항목 추가
# =============================================================================
CONFIG = {
    "embedding_model": "gemini-embedding-001",   # v6와 동일해야 검색이 맞음
    "persist_dir": "chroma_db",                  # 로컬 테스트 기본값. Colab이면 Drive 경로로 교체
    "s_criteria_xlsx": "Docs/채점기준표/ESG_핵심지표_채점기준표_S(사회).xlsx",
    "s_criteria_sheet": "01_ESG통합진단마스터",
    "output_csv": "S_채점결과.csv",

    "retrieval_k": 15,             # S 항목은 보통 4개년 추이·복수 요건 확인이 필요해 v6 기본(10)보다 넉넉히
    "hybrid_weights": [0.5, 0.5],  # 팀 확정값 그대로 (v6 CONFIG와 동일, 튜닝 전 변경 금지)
    "bm25_keep_pos_tags": {"NNG", "NNP", "NNB", "VV", "VA", "SL", "SN", "SH"},  # v6보다 개선한 부분
    # (v6는 BM25를 조사 미필터 원형 형태소로 만듦. 이 필터링은 검색 시점에만 적용되는
    #  계산이라 v6가 이미 저장한 데이터와 아무 충돌이 없어 안전하게 품질만 개선함.)

    "llm_model": "gemini-3.1-flash-lite",  # WBS 2-3-1의 "모델단일화·temp=0" 방침 반영.
    # (2026-09-03 팀 결정: 전체 채점 모델(ESG_Scoring_hybrid_v8_SKHY.ipynb)과 동일하게
    #  gemini-3.1-flash-lite로 통일. gemini-2.5-flash는 신규 사용자 대상 서비스 종료(404)로
    #  더 이상 사용 불가. 팀 확정 모델이 바뀌면 --llm-model로 override)
    "llm_temperature": 0,
    "evidence_char_limit": 700,       # 프롬프트에 넣는 청크당 최대 글자 수
}

RRF_K = 60
kiwi = Kiwi()


def kiwi_tokenize(text: str) -> list[str]:
    keep = CONFIG["bm25_keep_pos_tags"]
    return [t.form for t in kiwi.tokenize(text) if t.tag in keep]


# =============================================================================
# v6 스키마 호환 검색 계층 — v6 노트북(build_rag_index_v6_production.ipynb)의
# FilteredHybridRetriever/load_existing_index를 그대로 재현 (노트북은 import가
# 안 되므로 계약을 복제). base_metadata 필드명·doc_type 접미사 등은 전부 v6 그대로.
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

    def clear_cache(self):
        self._bm25_cache.clear()


def load_existing_index(persist_dir: Optional[str] = None):
    if not os.environ.get("GOOGLE_API_KEY"):
        sys.exit(
            "환경변수 GOOGLE_API_KEY가 설정되어 있지 않습니다.\n"
            "https://aistudio.google.com/apikey 에서 발급받아 설정하세요."
        )
    embeddings = GoogleGenerativeAIEmbeddings(model=CONFIG["embedding_model"])
    vectorstore = Chroma(
        persist_directory=persist_dir or CONFIG["persist_dir"],
        embedding_function=embeddings,
    )
    hybrid_retriever = FilteredHybridRetriever(vectorstore=vectorstore)
    return vectorstore, hybrid_retriever


def discover_indexed_companies(vectorstore) -> pd.DataFrame:
    """v6 인덱스에는 회사 목록(manifest)이 별도로 없으므로, 실제로 인덱싱된
    company_code/company_name을 Chroma 메타데이터에서 직접 뽑는다."""
    raw = vectorstore.get(include=["metadatas"])
    seen = {}
    for m in raw["metadatas"]:
        seen[m["company_code"]] = m.get("company_name", "")
    df = pd.DataFrame(
        [{"company_code": k, "company_name": v} for k, v in seen.items()]
    ).sort_values("company_code").reset_index(drop=True)
    return df


# =============================================================================
# S 채점기준표 로더 — 01_ESG통합진단마스터 시트를 헤더 행 자동탐색으로 파싱
# (열 위치를 하드코딩하지 않아 팀원이 열을 추가/이동해도 헤더명만 유지되면 안전)
# =============================================================================
# 실제 헤더 셀은 괄호로 부연설명이 붙거나("점검기준 상세(K-ESG v2.0 원문)"),
# 대괄호 접두어가 붙거나("[입력]위반유형1"), 단어 사이 공백이 다르게 들어가기도 해서
# ("실사 진단 질문" vs "실사진단질문") 정확히 일치시키지 않는다 — 공백 제거 후
# "핵심 키워드가 포함되어 있는가"로 판단한다 (아래 _normalize_header 참고).
S_ITEM_FIELDS = {
    "분류코드": "code",
    "적용구분": "apply_scope",
    "영역": "area",
    "범주": "category",
    "진단항목명": "name",
    "항목설명": "description",
    "데이터원천": "data_source",
    "데이터기간": "data_period",
    "데이터범위": "data_scope",
    "데이터산식": "formula",
    "채점유형": "scoring_type",
    "최대단계수": "max_levels",
    "배점구조요약": "score_structure",
    "점검기준상세": "criteria_detail",
    "KSSB대응현황": "kssb_status",
    "KSSB참고근거": "kssb_ref",
    "기타참고기준": "other_ref",
    "실사진단질문": "survey_question",
    "답변형식": "answer_format",
}


def _normalize_header(text: str) -> str:
    return "".join(str(text).split())  # 공백만 제거 (괄호/대괄호는 유지한 채 포함 여부로 매칭)


def load_s_criteria(xlsx_path: str, sheet_name: str = None) -> list[dict]:
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    ws = wb[sheet_name] if sheet_name else wb[CONFIG["s_criteria_sheet"]]

    norm_keys = {_normalize_header(k): field for k, field in S_ITEM_FIELDS.items()}

    header_row_idx, col_map = None, {}
    for r in range(1, min(ws.max_row, 10) + 1):
        hits = {}
        for c in range(1, ws.max_column + 1):
            v = ws.cell(r, c).value
            if not isinstance(v, str) or not v.strip():
                continue
            norm_v = _normalize_header(v)
            for norm_key, field in norm_keys.items():
                if norm_key in norm_v and field not in hits:
                    hits[field] = c
        if "code" in hits and "name" in hits:
            header_row_idx, col_map = r, hits
            break
    if header_row_idx is None:
        raise ValueError(f"{xlsx_path}: '분류코드'/'진단항목명' 헤더를 찾지 못함")

    missing = set(S_ITEM_FIELDS.values()) - set(col_map)
    if missing:
        print(f"[경고] 헤더에서 못 찾은 필드: {sorted(missing)} — 해당 항목은 빈 값으로 처리됨")

    items = []
    for r in range(header_row_idx + 1, ws.max_row + 1):
        code = ws.cell(r, col_map.get("code", 0)).value if "code" in col_map else None
        if not code or not str(code).strip().upper().startswith("S"):
            continue
        item = {field: ws.cell(r, c).value for field, c in col_map.items()}
        item["code"] = str(item["code"]).strip()
        item["max_levels"] = int(item["max_levels"]) if item.get("max_levels") else None
        items.append(item)

    if not items:
        raise ValueError(f"{xlsx_path}: S-* 항목을 하나도 못 찾음 (시트/헤더 확인 필요)")
    return items


# =============================================================================
# 배점 환산 — 단계형/선택형 공통 (N단계 등간 배점표)
# =============================================================================
def level_to_score(level: int, max_levels: int) -> int:
    """1단계=1점 ~ max_levels단계=100점, 등간격. (5단계: 1/25/50/75/100,
    3단계: 1/50/100, 2단계: 1/100 — 데이터팀 피드백 반영: 0점은 '미채점'과
    혼동되므로 최하위 단계도 1점 이상으로 표기.)"""
    if max_levels is None or max_levels < 2:
        return 1
    level = max(1, min(level, max_levels))
    return max(1, round(100 * (level - 1) / (max_levels - 1)))


# =============================================================================
# LLM 구조화 출력 스키마 (Pydantic) — "사실 판단은 LLM, 최종 산술은 파이썬" 원칙
# =============================================================================
class LevelAssessment(BaseModel):
    level: int = Field(description="근거로 뒷받침되는 가장 높은 단계/요건 번호 (1부터 시작)")
    rationale: str = Field(description="왜 이 단계인지, 어떤 하위 단계 조건까지 충족했는지 근거와 함께 한국어로 설명")
    evidence_chunk_ids: list[str] = Field(description="판단 근거로 실제 인용한 청크의 chunk_id 목록")
    insufficient_data: bool = Field(description="제공된 근거만으로 단계를 판단하기에 데이터가 불충분하면 true")
    confidence: Literal["high", "medium", "low"] = Field(description="이 판단에 대한 확신도")


class SubElementAssessment(BaseModel):
    label: str = Field(description="어떤 하위요소/요건에 대한 판단인지 (예: '재무적 지원 추세', '요건1: CISO 선임')")
    points: int = Field(description="이 하위요소가 전체 100점 만점에 기여하는 실제 배점(가중치 반영 완료 값). 규정된 배점표를 정확히 따를 것")
    rationale: str
    evidence_chunk_ids: list[str]
    insufficient_data: bool


class CompositeAssessment(BaseModel):
    sub_elements: list[SubElementAssessment]
    confidence: Literal["high", "medium", "low"]


class ViolationEntry(BaseModel):
    violation_type: Literal[1, 2, 3] = Field(description="1=사법상 형벌/벌금/과료·입찰제한, 2=행정상 금전적 처분, 3=행정상 비금전적 처분")
    description: str
    evidence_chunk_ids: list[str]


class DeductionAssessment(BaseModel):
    violations: list[ViolationEntry] = Field(description="확인된 위반 사실 목록. 위반이 없으면 빈 리스트")
    confidence: Literal["high", "medium", "low"]
    insufficient_data: bool = Field(description="위반 여부를 판단할 근거 자체가 부족하면 true (위반 없음과는 다름 — 무판단 상태)")


DEDUCTION_POINTS = {1: 50, 2: 30, 3: 10}


# =============================================================================
# 검색 — 항목별 쿼리 구성 및 근거 조회
# =============================================================================
def build_query(item: dict) -> str:
    parts = [item.get("name") or "", item.get("description") or "", item.get("survey_question") or ""]
    return " ".join(p.strip() for p in parts if p and str(p).strip())[:800]


def format_evidence(docs: list[Document]) -> str:
    if not docs:
        return "(검색된 근거 없음)"
    limit = CONFIG["evidence_char_limit"]
    blocks = []
    for d in docs:
        m = d.metadata
        blocks.append(
            f"[chunk_id={m.get('chunk_id')}] ({m.get('doc_type')}, p.{m.get('page')}, "
            f"섹션:{m.get('section_title') or '-'})\n{d.page_content[:limit]}"
        )
    return "\n\n".join(blocks)


# =============================================================================
# 프롬프트
# =============================================================================
LEVEL_PROMPT = """당신은 ESG 사회(S) 영역 채점 담당자입니다. 아래 진단항목의 충족단계별 요건과
실제 검색된 보고서 근거를 비교해서, 근거로 명확히 뒷받침되는 "가장 높은" 단계를 고르세요.
한 단계라도 조건이 불명확하면 그 아래 단계로 보수적으로 판단하세요. 근거에 없는 내용을
추측하거나 만들어내지 마세요.

[진단항목] {code} — {name}
[항목설명] {description}
[데이터기간/범위] {data_period} / {data_scope}
[충족단계별 요건]
{criteria_detail}
[배점구조] {score_structure} (최대 {max_levels}단계)

[검색된 근거 (기업: {company_name}, {company_code})]
{evidence}

위 요건과 근거를 비교해서 판단하세요. evidence_chunk_ids에는 실제로 판단에 사용한
chunk_id만 정확히 적으세요(존재하지 않는 id를 지어내지 마세요)."""

COMPOSITE_PROMPT = """당신은 ESG 사회(S) 영역 채점 담당자입니다. 아래 진단항목은 여러
하위요소로 구성된 복합가중형 항목입니다. 항목설명에 각 하위요소의 판단 기준과 배점이
이미 명시되어 있습니다 — 그 배점표를 정확히 따라서 하위요소마다 points를 매기세요
(임의로 점수를 만들지 말고, 명시된 배점 후보값 중에서만 고르세요). 모든 하위요소의
points 합이 최종 점수가 되므로, 가중치가 이미 반영된 값을 반환해야 합니다.

[진단항목] {code} — {name}
[항목설명 — 하위요소별 판단기준·배점 포함] {description}
[데이터산식] {formula}
[충족단계별 요건 상세]
{criteria_detail}
[배점구조 요약] {score_structure}

[검색된 근거 (기업: {company_name}, {company_code})]
{evidence}

항목설명에 언급된 모든 하위요소에 대해 빠짐없이 판단하세요."""

DEDUCTION_PROMPT = """당신은 ESG 사회(S) 영역 채점 담당자입니다. 아래 진단항목은 감점형
항목으로, 100점에서 시작해 위반 사실이 확인될 때마다 유형별로 감점합니다
(유형1 -50점, 유형2 -30점, 유형3 -10점, 중복 적용 가능). 위반이 확인되지 않으면
violations를 빈 리스트로 반환하세요 (이 경우 100점 처리됩니다). 근거에 명시적으로
나온 처분/제재만 위반으로 인정하고, 단순 이슈 제기나 소송 진행 중인 건은 포함하지
마세요(확정된 처분만).

[진단항목] {code} — {name}
[항목설명] {description}
[위반유형 정의]
{criteria_detail}
[데이터기간] {data_period}

[검색된 근거 (기업: {company_name}, {company_code})]
{evidence}"""


# =============================================================================
# LLM 호출 (재시도 포함)
# =============================================================================
@retry(
    wait=wait_exponential(multiplier=2, min=5, max=60),
    stop=stop_after_attempt(4),
    retry=retry_if_exception_message(match=".*RESOURCE_EXHAUSTED.*|.*429.*|.*rate limit.*|.*timeout.*"),
    reraise=True,
)
def _invoke_structured(llm, schema, prompt: str):
    return llm.with_structured_output(schema).invoke(prompt)


# =============================================================================
# 항목별 채점
# =============================================================================
def score_level_item(llm, retriever, item: dict, company_code: str, company_name: str) -> dict:
    query = build_query(item)
    docs = retriever.invoke(query, filter={"company_code": company_code}, top_n=CONFIG["retrieval_k"])
    prompt = LEVEL_PROMPT.format(
        code=item["code"], name=item.get("name", ""), description=item.get("description", ""),
        data_period=item.get("data_period", ""), data_scope=item.get("data_scope", ""),
        criteria_detail=item.get("criteria_detail", ""), score_structure=item.get("score_structure", ""),
        max_levels=item.get("max_levels", ""), company_name=company_name, company_code=company_code,
        evidence=format_evidence(docs),
    )
    result: LevelAssessment = _invoke_structured(llm, LevelAssessment, prompt)
    score = level_to_score(result.level, item.get("max_levels"))

    need_review = (
        result.insufficient_data or result.confidence == "low" or not result.evidence_chunk_ids or not docs
    )
    return {
        "충족단계/요건수": f"{result.level}단계",
        "자사취득점수": score,
        "confidence": result.confidence,
        "insufficient_data": result.insufficient_data,
        "근거_chunk_ids": ";".join(result.evidence_chunk_ids),
        "rationale": result.rationale,
        "need_review": need_review,
        "retrieval_query": query,
        "n_evidence_retrieved": len(docs),
    }


def score_composite_item(llm, retriever, item: dict, company_code: str, company_name: str) -> dict:
    query = build_query(item)
    docs = retriever.invoke(query, filter={"company_code": company_code}, top_n=CONFIG["retrieval_k"])
    prompt = COMPOSITE_PROMPT.format(
        code=item["code"], name=item.get("name", ""), description=item.get("description", ""),
        formula=item.get("formula", ""), criteria_detail=item.get("criteria_detail", ""),
        score_structure=item.get("score_structure", ""), company_name=company_name, company_code=company_code,
        evidence=format_evidence(docs),
    )
    result: CompositeAssessment = _invoke_structured(llm, CompositeAssessment, prompt)

    raw_total = sum(se.points for se in result.sub_elements)
    score = max(0, min(100, round(raw_total)))
    any_insufficient = any(se.insufficient_data for se in result.sub_elements) or not result.sub_elements
    all_chunk_ids = ";".join(sorted({cid for se in result.sub_elements for cid in se.evidence_chunk_ids}))
    breakdown = " | ".join(f"{se.label}: {se.points}점" for se in result.sub_elements)

    need_review = (
        any_insufficient or result.confidence == "low" or not all_chunk_ids or not docs
        or raw_total != score  # clamp가 실제로 발동했으면(=100점 초과 산출) review 대상
    )
    return {
        "충족단계/요건수": "해당없음(복합가중형)",
        "자사취득점수": score,
        "confidence": result.confidence,
        "insufficient_data": any_insufficient,
        "근거_chunk_ids": all_chunk_ids,
        "rationale": breakdown,
        "need_review": need_review,
        "retrieval_query": query,
        "n_evidence_retrieved": len(docs),
    }


def score_deduction_item(llm, retriever, item: dict, company_code: str, company_name: str) -> dict:
    query = build_query(item)
    docs = retriever.invoke(query, filter={"company_code": company_code}, top_n=CONFIG["retrieval_k"])
    prompt = DEDUCTION_PROMPT.format(
        code=item["code"], name=item.get("name", ""), description=item.get("description", ""),
        criteria_detail=item.get("criteria_detail", ""), data_period=item.get("data_period", ""),
        company_name=company_name, company_code=company_code, evidence=format_evidence(docs),
    )
    result: DeductionAssessment = _invoke_structured(llm, DeductionAssessment, prompt)

    deduction = sum(DEDUCTION_POINTS[v.violation_type] for v in result.violations)
    score = max(0, 100 - deduction)
    type_counts = {t: sum(1 for v in result.violations if v.violation_type == t) for t in (1, 2, 3)}
    all_chunk_ids = ";".join(sorted({cid for v in result.violations for cid in v.evidence_chunk_ids}))

    need_review = (
        result.insufficient_data or result.confidence == "low"
        or (result.violations and not all_chunk_ids) or not docs
    )
    return {
        "충족단계/요건수": f"위반 {len(result.violations)}건" if result.violations else "위반 없음",
        "위반유형1": type_counts[1], "위반유형2": type_counts[2], "위반유형3": type_counts[3],
        "자사취득점수": score,
        "confidence": result.confidence,
        "insufficient_data": result.insufficient_data,
        "근거_chunk_ids": all_chunk_ids,
        "rationale": " / ".join(v.description for v in result.violations) or "확인된 위반 없음",
        "need_review": need_review,
        "retrieval_query": query,
        "n_evidence_retrieved": len(docs),
    }


SCORERS = {
    "단계형": score_level_item,
    "선택형": score_level_item,   # 요건 누적 충족 = 단계형과 동일한 등간 배점표 로직
    "복합가중형": score_composite_item,
    "감점형": score_deduction_item,
}


def score_item(llm, retriever, item: dict, company_code: str, company_name: str) -> dict:
    scoring_type = (item.get("scoring_type") or "").strip()
    scorer = SCORERS.get(scoring_type)
    if scorer is None:
        return {
            "충족단계/요건수": "", "자사취득점수": None, "confidence": "low",
            "insufficient_data": True, "근거_chunk_ids": "", "rationale": f"알 수 없는 채점유형: {scoring_type!r}",
            "need_review": True, "retrieval_query": "", "n_evidence_retrieved": 0,
        }
    try:
        row = scorer(llm, retriever, item, company_code, company_name)
    except Exception as e:
        row = {
            "충족단계/요건수": "", "자사취득점수": None, "confidence": "low",
            "insufficient_data": True, "근거_chunk_ids": "", "rationale": f"채점 실패: {e}",
            "need_review": True, "retrieval_query": build_query(item), "n_evidence_retrieved": 0,
        }
    row.update({
        "company_code": company_code, "company_name": company_name,
        "분류코드": item["code"], "항목명": item.get("name", ""), "영역": item.get("area", ""),
        "범주": item.get("category", ""), "적용구분": item.get("apply_scope", ""),
        "채점유형": scoring_type, "채점시각": datetime.now(timezone.utc).isoformat(),
    })
    return row


# =============================================================================
# 드라이버
# =============================================================================
def score_company(llm, retriever, items: list[dict], company_code: str, company_name: str) -> pd.DataFrame:
    rows = [score_item(llm, retriever, item, company_code, company_name) for item in items]
    return pd.DataFrame(rows)


def score_all(llm, retriever, items: list[dict], companies: pd.DataFrame) -> pd.DataFrame:
    all_rows = []
    for _, row in companies.iterrows():
        print(f"[S 채점] {row['company_code']} {row['company_name']} — {len(items)}개 항목")
        df = score_company(llm, retriever, items, row["company_code"], row["company_name"])
        all_rows.append(df)
        n_flagged = df["need_review"].sum()
        print(f"  -> 완료, need_review 플래그 {n_flagged}/{len(df)}건")
    return pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame()


COLUMN_ORDER = [
    "company_code", "company_name", "분류코드", "항목명", "영역", "범주", "적용구분", "채점유형",
    "충족단계/요건수", "위반유형1", "위반유형2", "위반유형3", "자사취득점수",
    "confidence", "insufficient_data", "need_review", "근거_chunk_ids", "rationale",
    "retrieval_query", "n_evidence_retrieved", "채점시각",
]


def main():
    parser = argparse.ArgumentParser(description="ESG RAG S(사회) 개별 레이어 — 34개 항목 자동 채점")
    parser.add_argument("--persist-dir", default=CONFIG["persist_dir"], help="v6가 만든 Chroma persist_directory")
    parser.add_argument("--xlsx", default=CONFIG["s_criteria_xlsx"])
    parser.add_argument("--output-csv", default=CONFIG["output_csv"])
    parser.add_argument("--company-code", default=None, help="단일 회사만 채점 (미지정 시 인덱스 내 전체)")
    parser.add_argument("--llm-model", default=CONFIG["llm_model"])
    parser.add_argument("--item-codes", default=None,
                         help="쉼표로 구분한 분류코드만 채점 (예: S-1-1,S-2-1,S-8-2) — 스모크테스트용, 비용 통제")
    args = parser.parse_args()

    CONFIG["llm_model"] = args.llm_model

    print("=== S(사회) 채점기준표 로딩 ===")
    items = load_s_criteria(args.xlsx)
    print(f"  {len(items)}개 S-* 항목 로드 완료")

    if args.item_codes:
        wanted = {c.strip() for c in args.item_codes.split(",")}
        items = [it for it in items if it["code"] in wanted]
        missing = wanted - {it["code"] for it in items}
        if missing:
            print(f"  [경고] 못 찾은 분류코드: {sorted(missing)}")
        print(f"  --item-codes 필터 적용: {len(items)}개 항목만 채점")

    print("=== 인덱스 로딩 ===")
    vectorstore, retriever = load_existing_index(args.persist_dir)

    if args.company_code:
        companies = discover_indexed_companies(vectorstore)
        companies = companies[companies["company_code"] == args.company_code]
        if companies.empty:
            sys.exit(f"인덱스에 회사코드 {args.company_code}가 없습니다.")
    else:
        companies = discover_indexed_companies(vectorstore)
        print(f"  인덱스에 존재하는 회사 {len(companies)}개사 발견 (전체 91문항 대상 회사 목록과 다를 수 있음 — "
              f"v6에는 별도 회사 로스터가 없어 인덱스 내용 그대로 사용)")

    llm = ChatGoogleGenerativeAI(model=CONFIG["llm_model"], temperature=CONFIG["llm_temperature"])

    result_df = score_all(llm, retriever, items, companies)
    if result_df.empty:
        sys.exit("채점 결과가 비어 있습니다 (대상 회사 없음).")

    result_df = result_df[[c for c in COLUMN_ORDER if c in result_df.columns]]
    result_df.to_csv(args.output_csv, index=False, encoding="utf-8-sig")

    print(f"\n=== 완료: {len(result_df)}행 ({companies.shape[0]}개사 x {len(items)}항목) ===")
    print(f"저장 위치: {args.output_csv}")
    print(f"need_review 플래그: {int(result_df['need_review'].sum())}건 "
          f"({result_df['need_review'].sum() / len(result_df):.1%})")


if __name__ == "__main__":
    main()
