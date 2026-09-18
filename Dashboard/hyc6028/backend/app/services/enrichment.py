import re
from datetime import date

from app.db import get_supabase
from app.schemas import DdayInfo, GradeTrendRow, YearGrade
from app.schemas_extra import (
    BenchmarkCompany,
    CompanyProfile,
    RoadmapPlanResponse,
    RoadmapStageV2,
    RoadmapTaskV2,
    UrgencyCriteriaResponse,
)

URGENCY_RANK = {"즉시": 0, "중기": 1, "장기": 2}

_TIER_RE = re.compile(r"(\d)차\s*구간")
_APPLY_YEAR_RE = re.compile(r"(\d{4})년\(FY\d+\)부터\s*적용")
_PREP_RANGE_RE = re.compile(r"체계\s*구축\s*기간은\s*(\d{4})~(\d{4})년\s*(\d+)년")
_FIRST_DISCLOSURE_RE = re.compile(r"(\d{4})년이\s*첫\s*공시\s*대상")

_CODE_SPLIT_RE = re.compile(r"[·,]")


def expand_related_codes(raw_codes: list[str] | None) -> list[str]:
    """related_item_codes 항목은 코드 여러 개가 한 문자열에 묶여 있을 수 있다
    (예: '반도체-E-1·E-2·E-4·E-5') 혹은 코드가 아닐 수 있다('비채점과제', 'P 영역 전체')."""
    out: list[str] = []
    for c in raw_codes or []:
        out.extend(p.strip() for p in _CODE_SPLIT_RE.split(c) if p.strip())
    return out


def get_company_id(company: str) -> int | None:
    supabase = get_supabase()
    res = supabase.table("esg_companies").select("id").eq("name", company).limit(1).execute()
    return res.data[0]["id"] if res.data else None


def compute_dday(company: str) -> DdayInfo | None:
    """esg_disclosure_deadline의 '고객사 해당 구간'/'실질 준비 기간' 텍스트를 정규식으로 파싱해
    의무공시 착수 기한(D-day)을 실계산한다. 데이터가 없는 회사는 None을 반환한다."""
    company_id = get_company_id(company)
    if company_id is None:
        return None
    supabase = get_supabase()
    res = (
        supabase.table("esg_disclosure_deadline")
        .select("key, value")
        .eq("company_id", company_id)
        .execute()
    )
    if not res.data:
        return None
    rows = {r["key"]: r["value"] for r in res.data}
    tier_text = rows.get("고객사 해당 구간", "")
    prep_text = rows.get("실질 준비 기간", "")

    tier_m = _TIER_RE.search(tier_text)
    apply_m = _APPLY_YEAR_RE.search(tier_text)
    prep_m = _PREP_RANGE_RE.search(prep_text)
    first_m = _FIRST_DISCLOSURE_RE.search(prep_text)

    tier = int(tier_m.group(1)) if tier_m else None
    apply_year = int(apply_m.group(1)) if apply_m else (int(first_m.group(1)) if first_m else None)
    build_start_year = int(prep_m.group(1)) if prep_m else None
    build_end_year = int(prep_m.group(2)) if prep_m else None
    prep_years = int(prep_m.group(3)) if prep_m else None

    deadline_date = date(build_end_year, 12, 31) if build_end_year else None
    days_left = (deadline_date - date.today()).days if deadline_date else None

    return DdayInfo(
        tier=tier,
        apply_year=apply_year,
        build_start_year=build_start_year,
        build_end_year=build_end_year,
        prep_years=prep_years,
        deadline_date=deadline_date.isoformat() if deadline_date else None,
        days_left=days_left,
        tier_text=tier_text or None,
        prep_text=prep_text or None,
    )


def get_company_profile(company: str) -> CompanyProfile | None:
    company_id = get_company_id(company)
    if company_id is None:
        return None
    supabase = get_supabase()
    res = (
        supabase.table("esg_company_profile")
        .select("*")
        .eq("company_id", company_id)
        .limit(1)
        .execute()
    )
    if not res.data:
        return None
    r = res.data[0]
    return CompanyProfile(
        stock_code=r.get("stock_code"),
        founded_year=r.get("설립연도"),
        listing=r.get("상장구분"),
        main_business=r.get("주요사업"),
        total_assets=r.get("연결자산총액"),
        industry_class=r.get("업종분류"),
        employees=r.get("종업원수"),
    )


def get_benchmark_companies(company: str) -> list[BenchmarkCompany]:
    company_id = get_company_id(company)
    if company_id is None:
        return []
    supabase = get_supabase()
    res = (
        supabase.table("esg_benchmark_companies")
        .select("*")
        .eq("company_id", company_id)
        .order("benchmark_label")
        .execute()
    )
    return [
        BenchmarkCompany(
            benchmark_label=r["benchmark_label"],
            industry=r.get("industry"),
            grade_2025=r.get("grade_2025"),
            rationale=r.get("rationale"),
        )
        for r in (res.data or [])
    ]


def get_urgency_criteria(company: str) -> UrgencyCriteriaResponse:
    company_id = get_company_id(company)
    if company_id is None:
        return UrgencyCriteriaResponse(criteria={})
    supabase = get_supabase()
    res = (
        supabase.table("esg_urgency_criteria")
        .select("level, criteria")
        .eq("company_id", company_id)
        .execute()
    )
    return UrgencyCriteriaResponse(criteria={r["level"]: r["criteria"] for r in (res.data or [])})


def get_item_narrative(company: str, item_code: str) -> dict | None:
    """단일 항목의 narrative row(dict)를 반환한다. build_item_detail에서 사용."""
    company_id = get_company_id(company)
    if company_id is None:
        return None
    supabase = get_supabase()
    res = (
        supabase.table("esg_item_narrative")
        .select("*")
        .eq("company_id", company_id)
        .eq("item_code", item_code)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


def get_kcgs_grade_trend(company: str) -> tuple[list[GradeTrendRow], str | None]:
    """esg_kcgs_grades에서 자사+벤치마킹 등급 추이를 조립한다.
    반환: (grade_trend 목록, 최신연도 자사 종합등급)
    """
    company_id = get_company_id(company)
    if company_id is None:
        return [], None
    supabase = get_supabase()
    res = (
        supabase.table("esg_kcgs_grades")
        .select("*")
        .eq("company_id", company_id)
        .order("year")
        .execute()
    )
    rows = res.data or []
    if not rows:
        return [], None

    def to_year_grade(r: dict) -> YearGrade:
        return YearGrade(overall=r.get("grade_overall"), e=r.get("grade_e"), s=r.get("grade_s"), g=r.get("grade_g"))

    self_rows = [r for r in rows if not r["is_benchmark"]]
    self_grades = {str(r["year"]): to_year_grade(r) for r in self_rows}
    grade_trend = [GradeTrendRow(alias="자사", self_company=True, grades=self_grades)]

    by_alias: dict[str, dict[str, YearGrade]] = {}
    for r in rows:
        if not r["is_benchmark"]:
            continue
        by_alias.setdefault(r["benchmark_label"], {})[str(r["year"])] = to_year_grade(r)
    for alias, grades in sorted(by_alias.items()):
        grade_trend.append(GradeTrendRow(alias=alias, self_company=False, grades=grades))

    latest_self = max(self_rows, key=lambda r: r["year"]) if self_rows else None
    official_grade = latest_self["grade_overall"] if latest_self else None
    return grade_trend, official_grade


def get_roadmap_plan(company: str) -> RoadmapPlanResponse | None:
    """esg_roadmap_stages + esg_roadmap_tasks를 조립하고, 각 과제의 related_item_codes를
    esg_diagnostic_scores.urgency와 조인해 개별 코드별 시급성과 '최고 시급성' 배지 값을 계산한다."""
    company_id = get_company_id(company)
    if company_id is None:
        return None
    supabase = get_supabase()

    stage_res = (
        supabase.table("esg_roadmap_stages")
        .select("*")
        .eq("company_id", company_id)
        .order("stage_no")
        .execute()
    )
    if not stage_res.data:
        return None

    task_res = (
        supabase.table("esg_roadmap_tasks")
        .select("*")
        .eq("company_id", company_id)
        .execute()
    )

    # 실제 채점 항목의 urgency 맵 (item_code -> urgency)
    diag_res = (
        supabase.table("esg_diagnostic_scores")
        .select("item_code, urgency")
        .eq("company_id", company_id)
        .execute()
    )
    urgency_by_code = {r["item_code"]: r["urgency"] for r in (diag_res.data or []) if r.get("urgency")}

    tasks_by_stage: dict[str, list[RoadmapTaskV2]] = {}
    for t in task_res.data or []:
        codes = expand_related_codes(t.get("related_item_codes"))
        code_urgencies = []
        for code in codes:
            u = urgency_by_code.get(code)
            if u:
                code_urgencies.append({"code": code, "urgency": u})
        worst = None
        if code_urgencies:
            worst = min((c["urgency"] for c in code_urgencies), key=lambda u: URGENCY_RANK.get(u, 9))
        task = RoadmapTaskV2(
            task_name=t["task_name"],
            related_item_codes=t.get("related_item_codes") or [],
            deliverables=t.get("deliverables"),
            code_urgencies=code_urgencies,
            worst_urgency=worst,
        )
        tasks_by_stage.setdefault(str(t["stage_no"]), []).append(task)

    stages = []
    for s in stage_res.data:
        stage_no = str(s["stage_no"])
        stages.append(
            RoadmapStageV2(
                stage_no=stage_no,
                year=s.get("year"),
                stage_name=s.get("stage_name"),
                urgency_level=s.get("urgency_level"),
                tasks=tasks_by_stage.get(stage_no, []),
            )
        )
    return RoadmapPlanResponse(stages=stages)
