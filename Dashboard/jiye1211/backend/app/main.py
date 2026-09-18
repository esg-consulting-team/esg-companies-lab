"""ESG 통합 진단 센터 API (L1~L3 MVP).

사양서: db/ESG_대시보드_전체화면_사양서_v2.md
데이터: Supabase `esg_diagnosis` 테이블 (DN오토모티브 · 하나마이크론, 각 42개 항목)
"""
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import company_profile, evidence_docs, rag, repository, roadmap
from .cache_utils import clear_all_caches
from .config import get_settings
from .parsing import DOMAIN_BUCKETS

app = FastAPI(title="ESG 통합 진단 센터 API", version="0.1.0")

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    # Vite는 5173이 사용 중이면 5174, 5175...로 자동으로 넘어가므로, 개발 편의를 위해
    # localhost/127.0.0.1의 아무 포트나 추가로 허용한다 (운영 배포 시에는 이 앱을 그대로 쓰지 말 것).
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1):\d+$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/admin/clear-cache")
def clear_cache() -> dict:
    """개발용 — 인증 없음, 로컬 전용. Supabase 데이터를 직접 고친 뒤 TTL(기본 5분)을
    기다리지 않고 바로 반영하고 싶을 때 호출한다(backend/app/cache_utils.py 참고)."""
    cleared = clear_all_caches()
    return {"status": "ok", "clearedEntries": cleared}


@app.get("/api/companies")
def list_companies() -> list[dict]:
    from .mock_data import get_company_profile

    names = repository.fetch_companies()
    return [
        {
            "name": name,
            "sector": get_company_profile(name).get("sector"),
            "id": get_company_profile(name).get("companyId"),
        }
        for name in names
    ]


@app.get("/api/companies/{company}/summary")
def company_summary(company: str) -> dict:
    names = repository.fetch_companies()
    if company not in names:
        raise HTTPException(status_code=404, detail=f"'{company}' 회사 데이터를 찾을 수 없습니다.")
    return repository.build_summary(company)


@app.get("/api/companies/{company}/items")
def company_items(company: str) -> list[dict]:
    names = repository.fetch_companies()
    if company not in names:
        raise HTTPException(status_code=404, detail=f"'{company}' 회사 데이터를 찾을 수 없습니다.")
    rows = repository.fetch_rows(company)
    return [repository.normalize_item(r) for r in rows]


@app.get("/api/companies/{company}/domains/{bucket}")
def company_domain_detail(company: str, bucket: str) -> dict:
    if bucket not in DOMAIN_BUCKETS:
        raise HTTPException(
            status_code=404,
            detail=f"알 수 없는 영역 '{bucket}'. 사용 가능: {list(DOMAIN_BUCKETS)}",
        )
    names = repository.fetch_companies()
    if company not in names:
        raise HTTPException(status_code=404, detail=f"'{company}' 회사 데이터를 찾을 수 없습니다.")
    return repository.build_domain_detail(company, bucket)


@app.get("/api/companies/{company}/items/{code}")
def company_item_detail(company: str, code: str) -> dict:
    detail = repository.build_item_detail(company, code)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"항목 '{code}'를 찾을 수 없습니다.")
    return detail


@app.get("/api/companies/{company}/report-comparison")
def company_report_comparison(company: str) -> dict:
    """L4 비교 분석 — 컨설팅 보고서(docx)에서 검증한 그룹비교·선례·KCGS 상관도 데이터.
    db/report_extracted_data.json이 정답 데이터이며, 없는 회사·필드는 null로 내려간다."""
    data = repository.build_report_comparison(company)
    if data is None:
        raise HTTPException(status_code=404, detail=f"'{company}'에 대한 보고서 비교 데이터가 없습니다.")
    return data


@app.get("/api/companies/{company}/domain-benchmark")
def company_domain_benchmark(company: str) -> dict:
    """L4 "자사 vs 벤치마킹군" Exhibit — company_esg_yearly 기준 자사 + 벤치마킹사 도메인별 채점값.
    벤치마킹 매핑은 backend/app/benchmark_config.py에서 관리한다."""
    return repository.fetch_domain_benchmark(company)


@app.get("/api/companies/{company}/roadmap")
def company_roadmap(company: str) -> dict:
    """L5 개선 로드맵 — esg_roadmap_stages/esg_roadmap_tasks/esg_urgency_criteria/esg_disclosure_deadline
    (Supabase) 기준 4단계 실행 로드맵. esg_companies에 해당 회사가 없으면 404."""
    data = roadmap.build_roadmap(company)
    if data is None:
        raise HTTPException(status_code=404, detail=f"'{company}'에 대한 로드맵 데이터가 없습니다.")
    return data


@app.get("/api/companies/{company}/evidence-documents")
def company_evidence_documents(company: str) -> dict:
    """L6 Exhibit 1 — 채점 근거 텍스트에서 키워드로 추출한 참고자료 유형별 연결 항목 수(근사치)."""
    names = repository.fetch_companies()
    if company not in names:
        raise HTTPException(status_code=404, detail=f"'{company}' 회사 데이터를 찾을 수 없습니다.")
    return evidence_docs.build_document_coverage(company)


@app.get("/api/companies/{company}/evidence-gaps")
def company_evidence_gaps(company: str) -> list[dict]:
    """L6 Exhibit 2 — 근거충분성이 불충분/부분인 항목 목록 (evidence_level() 재사용)."""
    names = repository.fetch_companies()
    if company not in names:
        raise HTTPException(status_code=404, detail=f"'{company}' 회사 데이터를 찾을 수 없습니다.")
    return evidence_docs.build_evidence_gaps(company)


@app.get("/api/companies/{company}/profile-card")
def company_profile_card(company: str) -> dict:
    """L7 표지 — esg_company_profile 원본 필드 그대로(계산 없음). 행이 없으면 404."""
    card = company_profile.fetch_company_profile_card(company)
    if card is None:
        raise HTTPException(status_code=404, detail=f"'{company}'에 대한 프로필 데이터가 없습니다.")
    return card


class ChatHistoryTurn(BaseModel):
    question: str
    conclusion: str


class ChatRequest(BaseModel):
    company: str
    question: str
    itemCode: Optional[str] = None
    history: Optional[list[ChatHistoryTurn]] = None


_ITEM_CONTEXT_FIELDS = [
    "code",
    "name",
    "category",
    "domainLabel",
    "score",
    "evidence",
    "urgency",
    "criteriaDetail",
    "dataSource",
    "scoringNote",
    "solutionSplit",
]


@app.post("/api/chat")
def chat(req: ChatRequest) -> dict:
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="질문이 비어 있습니다.")
    item_ctx = None
    if req.itemCode:
        detail = repository.build_item_detail(req.company, req.itemCode)
        if detail:
            item_ctx = {k: detail.get(k) for k in _ITEM_CONTEXT_FIELDS}
    history = [h.model_dump() for h in req.history] if req.history else None
    return rag.answer_question(req.company, req.question, item_context=item_ctx, history=history)


@app.get("/api/rag/status")
def rag_status() -> dict:
    return rag.index_status()
