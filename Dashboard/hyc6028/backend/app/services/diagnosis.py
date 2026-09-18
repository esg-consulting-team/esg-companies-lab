import re

from app.db import get_supabase
from app.schemas import (
    CompanyMeta,
    DashboardSummary,
    DomainItemsResponse,
    DomainSummary,
    EvidenceBlock,
    GapItem,
    ImmediateTask,
    ItemDetail,
    ItemHeatCell,
    KpiSummary,
    NarrativeBlock,
    SolutionBlock,
    UrgencyCounts,
)
from app.services import enrichment

DOMAIN_LABELS = {
    "disclosure": "정보공시",
    "environment": "환경 E",
    "governance": "지배구조 G",
    "sector": "업종특화",
}
DOMAIN_ORDER = ["disclosure", "environment", "governance", "sector"]

_SOLUTION_MARKER_RE = re.compile(r"\[(26년\s*현황|개선방향|필요\s*근거)\]\s*")


def map_domain_key(row: dict) -> str:
    """항목의 도메인 분류. apply_type에 '업종특화'가 포함되거나 '반도체-' 코드인 항목은
    업종특화로 별도 분리한다 (esg_diagnostic_items.apply_type 기준)."""
    code = row.get("category_code") or ""
    apply_type = row.get("apply_type") or ""
    if "업종특화" in apply_type or code.startswith("반도체"):
        return "sector"
    domain = row.get("domain")
    if domain == "정보공시":
        return "disclosure"
    if domain == "환경":
        return "environment"
    if domain == "지배구조":
        return "governance"
    return "other"


def parse_evidence(text: str | None) -> EvidenceBlock:
    """'비고-채점모델' 필드(예: '[자동채점] | 근거충분성: 충분 | 근거: ... | 근거페이지: ...')를 분해한다."""
    if not text:
        return EvidenceBlock(evidence_sufficiency="미확인")
    data: dict[str, str] = {}
    for segment in text.split("|"):
        segment = segment.strip()
        if ":" in segment:
            key, _, value = segment.partition(":")
            data[key.strip()] = value.strip()
    return EvidenceBlock(
        evidence_sufficiency=data.get("근거충분성", "미확인"),
        confirmed_basis=data.get("근거"),
        reference_pages=data.get("근거페이지"),
    )


def parse_solution(text: str | None) -> SolutionBlock:
    """'해결방안' 필드를 [26년 현황]/[개선방향]/[필요 근거] 3분할로 분해한다."""
    if not text:
        return SolutionBlock()
    parts = _SOLUTION_MARKER_RE.split(text)
    result: dict[str, str] = {}
    values = iter(parts[1:])
    for marker, content in zip(values, values):
        key = marker.replace(" ", "")
        result[key] = content.strip()
    return SolutionBlock(
        current_problem=result.get("26년현황"),
        direction=result.get("개선방향"),
        required_evidence=result.get("필요근거"),
    )


def fetch_items(company: str) -> list[dict]:
    """esg_diagnostic_scores를 esg_diagnostic_items와 조인해 조회한다
    (구 평면 테이블 esg_diagnosis 대신 ESG_handoff와 동일한 정규화 스키마 사용).

    반환 dict의 키 이름은 이 모듈과 하위 서비스(roadmap/documents/reports)가 기대하는
    기존 필드명(category_code, domain, note_scoring_model 등)으로 맞춰서 내려준다.
    """
    company_id = enrichment.get_company_id(company)
    if company_id is None:
        return []
    supabase = get_supabase()
    res = (
        supabase.table("esg_diagnostic_scores")
        .select(
            "item_code,fulfilled_level,violation_type_1,violation_type_2,violation_type_3,"
            "score,note_2025,note_2026,urgency,solution,"
            "esg_diagnostic_items(item_name,area,apply_type,category,scoring_type,"
            "criteria_detail,kssb_status,kssb_reference,other_reference,"
            "improvement_guide,audit_question,answer_format)"
        )
        .eq("company_id", company_id)
        .execute()
    )
    merged = []
    for row in res.data or []:
        item = row.pop("esg_diagnostic_items") or {}
        merged.append(
            {
                **row,
                "category_code": row["item_code"],
                "item_name": item.get("item_name"),
                "domain": item.get("area"),
                "apply_type": item.get("apply_type"),
                "application_type": item.get("apply_type"),
                "category": item.get("category"),
                "scoring_type": item.get("scoring_type"),
                "criteria_detail": item.get("criteria_detail"),
                "kssb_status": item.get("kssb_status"),
                "kssb_reference": item.get("kssb_reference"),
                "other_reference_standards": item.get("other_reference"),
                "improvement_guide": item.get("improvement_guide"),
                "audit_question": item.get("audit_question"),
                "answer_format": item.get("answer_format"),
                "note_scoring_model": row.get("note_2025"),
                "note_ai_scoring": row.get("note_2026"),
            }
        )
    merged.sort(key=lambda r: r["category_code"])
    return merged


def list_companies() -> list[CompanyMeta]:
    supabase = get_supabase()
    res = supabase.table("company_meta").select("*").order("company").execute()
    return [CompanyMeta(**row) for row in (res.data or [])]


def build_dashboard_summary(company: str) -> DashboardSummary | None:
    all_items = fetch_items(company)
    if not all_items:
        return None
    # 업종특화 항목 중 해당 회사에 적용되지 않는 항목(score=null)은 집계에서 제외
    items = [r for r in all_items if r.get("score") is not None]

    supabase = get_supabase()

    grouped: dict[str, dict] = {}
    for row in items:
        key = map_domain_key(row)
        if key == "other":
            continue
        bucket = grouped.setdefault(key, {"items": 0, "achieved": 0.0})
        bucket["items"] += 1
        bucket["achieved"] += float(row.get("score") or 0)

    bench_res = (
        supabase.table("domain_benchmarks").select("*").eq("company", company).execute()
    )
    bench_map = {r["domain_key"]: r["benchmark_avg"] for r in (bench_res.data or [])}

    domains = []
    for key in DOMAIN_ORDER:
        bucket = grouped.get(key, {"items": 0, "achieved": 0.0})
        max_possible = bucket["items"] * 100
        rate = (bucket["achieved"] / max_possible) if max_possible else 0.0
        domains.append(
            DomainSummary(
                key=key,
                label=DOMAIN_LABELS[key],
                items=bucket["items"],
                achieved=bucket["achieved"],
                max_possible=max_possible,
                achievement_rate=rate,
                benchmark_avg=bench_map.get(key),
            )
        )

    total_score = sum(float(r.get("score") or 0) for r in items)
    max_score = len(items) * 100
    evidence_by_item = {r["category_code"]: parse_evidence(r.get("note_scoring_model")) for r in items}
    insufficient = sum(1 for ev in evidence_by_item.values() if ev.evidence_sufficiency == "불충분")
    recoverable = sum(
        1
        for r in items
        if evidence_by_item[r["category_code"]].evidence_sufficiency in ("불충분", "부분", "부분적")
        and float(r.get("score") or 0) < 100
    )

    ranked_by_loss = sorted(items, key=lambda r: -(100 - float(r.get("score") or 0)))
    gap_top = [
        GapItem(
            item_code=r["category_code"],
            item_name=r["item_name"],
            domain=r["domain"],
            score=float(r.get("score") or 0),
            lost_points=100 - float(r.get("score") or 0),
        )
        for r in ranked_by_loss[:5]
    ]

    urgency_counts = {"즉시": 0, "중기": 0, "장기": 0}
    for r in items:
        u = r.get("urgency")
        if u in urgency_counts:
            urgency_counts[u] += 1

    immediate = [r for r in ranked_by_loss if r.get("urgency") == "즉시"]
    immediate_tasks = []
    for r in immediate:
        sol = parse_solution(r.get("solution"))
        immediate_tasks.append(
            ImmediateTask(
                item_code=r["category_code"],
                item_name=r["item_name"],
                urgency=r.get("urgency") or "",
                score=float(r.get("score") or 0),
                lost_points=100 - float(r.get("score") or 0),
                direction=(sol.direction or "")[:400],
            )
        )

    meta_res = supabase.table("company_meta").select("*").eq("company", company).execute()
    meta_row = meta_res.data[0] if meta_res.data else {"company": company}
    company_meta = CompanyMeta(**meta_row)

    grade_trend, official_grade = enrichment.get_kcgs_grade_trend(company)
    dday = enrichment.compute_dday(company)

    doc_res = (
        supabase.table("documents").select("id", count="exact").eq("company", company).execute()
    )
    documents_count = doc_res.count or 0

    kpi = KpiSummary(
        total_score=total_score,
        max_score=max_score,
        achievement_rate=(total_score / max_score) if max_score else 0.0,
        insufficient_evidence_items=insufficient,
        applicable_items=len(items),
        recoverable_by_evidence=recoverable,
    )

    return DashboardSummary(
        company=company_meta,
        kpi=kpi,
        domains=domains,
        grade_trend=grade_trend,
        official_grade=official_grade,
        gap_top=gap_top,
        urgency_counts=UrgencyCounts(**urgency_counts),
        immediate_tasks=immediate_tasks,
        documents_count=documents_count,
        dday=dday,
    )


def build_domain_items(company: str, domain_key: str) -> DomainItemsResponse | None:
    if domain_key not in DOMAIN_LABELS:
        return None
    items = fetch_items(company)
    if not items:
        return None
    filtered = [
        r for r in items if map_domain_key(r) == domain_key and r.get("score") is not None
    ]
    cells = []
    for r in filtered:
        ev = parse_evidence(r.get("note_scoring_model"))
        cells.append(
            ItemHeatCell(
                item_code=r["category_code"],
                item_name=r["item_name"],
                category=r.get("category") or "",
                score=float(r.get("score") or 0),
                evidence_sufficiency=ev.evidence_sufficiency,
                urgency=r.get("urgency") or "",
                scoring_type=r.get("scoring_type") or "",
                sector_specific=(r.get("category_code") or "").startswith("반도체"),
            )
        )
    achieved = sum(c.score for c in cells)
    max_possible = len(cells) * 100
    return DomainItemsResponse(
        domain_key=domain_key,
        label=DOMAIN_LABELS[domain_key],
        items=cells,
        achieved=achieved,
        max_possible=max_possible,
    )


def build_item_detail(company: str, item_code: str) -> ItemDetail | None:
    items = fetch_items(company)
    r = next((row for row in items if row["category_code"] == item_code), None)
    if r is None:
        return None
    ev = parse_evidence(r.get("note_scoring_model"))
    ev.deduction_note = r.get("note_ai_scoring")
    sol = parse_solution(r.get("solution"))

    narrative_row = enrichment.get_item_narrative(company, item_code)
    narrative = (
        NarrativeBlock(
            fulfilled_level_text=narrative_row.get("fulfilled_level_text"),
            status=narrative_row.get("status"),
            improvement=narrative_row.get("improvement"),
            followup=narrative_row.get("followup"),
            benchmark_case=narrative_row.get("benchmark_case"),
        )
        if narrative_row
        else None
    )

    return ItemDetail(
        item_code=r["category_code"],
        item_name=r["item_name"],
        domain=r.get("domain") or "",
        category=r.get("category") or "",
        score=float(r.get("score") or 0),
        evidence_sufficiency=ev.evidence_sufficiency,
        urgency=r.get("urgency") or "",
        scoring_type=r.get("scoring_type") or "",
        application_type=r.get("application_type"),
        criteria_detail=r.get("criteria_detail"),
        guideline_background=r.get("improvement_guide"),
        evidence=ev,
        solution=sol,
        audit_question=r.get("audit_question"),
        answer_format=r.get("answer_format"),
        kssb_status=r.get("kssb_status"),
        kssb_reference=r.get("kssb_reference"),
        other_reference_standards=r.get("other_reference_standards"),
        narrative=narrative,
    )
