"""Supabase esg_diagnosis 테이블을 화면(L1/L2/L3)이 쓰는 형태로 가공한다."""
from typing import Any, Optional

from .benchmark_config import BENCHMARK_MAP
from .mock_data import INDUSTRY_NAMES, get_company_profile
from .parsing import DOMAIN_BUCKETS, bucket_of, evidence_level, extract_evidence_sources, parse_scoring_note, parse_solution
from .report_data import get_pending_item, get_report_comparison
from .supabase_client import get_supabase

ASSESSMENT_YEAR = 2026  # 원본 파일명 "...26년 현황..." 기준 단일 스냅샷
TABLE = "esg_diagnosis"
GRADE_YEARLY_TABLE = "company_esg_yearly"
COMPANIES_TABLE = "companies"


def _to_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fetch_companies() -> list[str]:
    sb = get_supabase()
    res = sb.table(TABLE).select("company").execute()
    seen: list[str] = []
    for row in res.data or []:
        c = row.get("company")
        if c and c not in seen:
            seen.append(c)
    return seen


def fetch_rows(company: str) -> list[dict[str, Any]]:
    sb = get_supabase()
    res = (
        sb.table(TABLE)
        .select("*")
        .eq("company", company)
        .order("no", desc=False)
        .execute()
    )
    return res.data or []


def fetch_company_code(company: str) -> Optional[str]:
    """앱에서 쓰는 회사명(esg_diagnosis.company 값)으로 companies.기업코드를 찾는다."""
    sb = get_supabase()
    res = sb.table(COMPANIES_TABLE).select("기업코드").eq("기업명", company).limit(1).execute()
    rows = res.data or []
    return rows[0]["기업코드"] if rows else None


def fetch_grade_history(company: str) -> list[dict[str, Any]]:
    """company_esg_yearly에서 이 회사의 최근 3개년 KCGS 공식등급을 연도 오름차순으로 가져온다.
    해당 연도 행이 없으면(신규 상장 등) 등급을 전부 null로 채워 자리만 유지한다 — 이전 연도 값으로
    임의 보간하지 않는다."""
    code = fetch_company_code(company)
    if code is None:
        return []
    sb = get_supabase()
    res = (
        sb.table(GRADE_YEARLY_TABLE)
        .select("평가년도, esg등급, esg환경, esg사회, esg지배구조")
        .eq("기업코드", code)
        .order("평가년도")
        .execute()
    )
    rows = res.data or []
    if not rows:
        return []

    by_year = {r["평가년도"]: r for r in rows}
    latest_year = max(by_year)
    target_years = [latest_year - 2, latest_year - 1, latest_year]

    history = []
    for year in target_years:
        r = by_year.get(year)
        history.append(
            {
                "year": year,
                "overall": r.get("esg등급") if r else None,
                "environment": r.get("esg환경") if r else None,
                "social": r.get("esg사회") if r else None,
                "governance": r.get("esg지배구조") if r else None,
            }
        )
    return history


def fetch_latest_domain_scores(company: str) -> Optional[dict[str, Any]]:
    """company_esg_yearly에서 이 회사의 최신 연도 도메인별 채점값을 가져온다.
    반도체 회사·비반도체 회사 구분 없이 동일한 컬럼(채점평균/채점공시/채점환경/채점지배구조)을 쓴다
    — "_반도체제외" 보정 컬럼은 여기서 쓰지 않는다."""
    code = fetch_company_code(company)
    if code is None:
        return None
    sb = get_supabase()
    res = (
        sb.table(GRADE_YEARLY_TABLE)
        .select("평가년도, 채점평균, 채점공시, 채점환경, 채점지배구조")
        .eq("기업코드", code)
        .order("평가년도", desc=True)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    if not rows:
        return None
    r = rows[0]
    return {
        "company": company,
        "year": r["평가년도"],
        "overall": r.get("채점평균"),
        "disclosure": r.get("채점공시"),
        "environment": r.get("채점환경"),
        "governance": r.get("채점지배구조"),
    }


def fetch_domain_benchmark(company: str) -> dict[str, Any]:
    """L4 "자사 vs 벤치마킹군" Exhibit용 — 자사 + BENCHMARK_MAP에 등록된 벤치마킹사들의
    최신 연도 도메인별 채점값(company_esg_yearly). 업종특화/반도체특화 도메인은 이 테이블에
    별도 컬럼이 없어 포함하지 않는다(임의로 값을 만들지 않음)."""
    self_scores = fetch_latest_domain_scores(company)
    peers = []
    for peer_name in BENCHMARK_MAP.get(company, []):
        peer_scores = fetch_latest_domain_scores(peer_name)
        if peer_scores is not None:
            peers.append(peer_scores)
    return {"self": self_scores, "peers": peers}


def compute_official_grade(grade_history: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """gradeHistory(연도 오름차순)에서 가장 최근 연도의 공식등급을 뽑는다. 등급이 없으면 None."""
    latest = grade_history[-1] if grade_history else None
    if latest and latest.get("overall"):
        return {"source": "KCGS", "year": latest["year"], "overall": latest["overall"]}
    return None


ASSET_TRILLION = 1_000_000_000_000  # 1조원


def fetch_latest_total_assets(company: str) -> Optional[float]:
    """company_esg_yearly에서 이 회사의 '최신 연도' 행 자산총액을 그대로 가져온다.
    다른 연도로 대체하거나 보간하지 않는다 — 최신 연도 행 자체에 값이 없으면 None."""
    code = fetch_company_code(company)
    if code is None:
        return None
    sb = get_supabase()
    res = (
        sb.table(GRADE_YEARLY_TABLE)
        .select("평가년도, 자산총액")
        .eq("기업코드", code)
        .order("평가년도", desc=True)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    if not rows or rows[0].get("자산총액") is None:
        return None
    return float(rows[0]["자산총액"])


def build_industry_profile(company: str) -> dict[str, Any]:
    """L1 상단 기업 프로필 한 줄 — companies(시장구분·산업코드) + company_esg_yearly 최신 연도
    (자산총액·자산기준군)를 조합한다. 업종명은 mock_data.INDUSTRY_NAMES에 확인된 코드만 채운다."""
    sb = get_supabase()
    static_res = sb.table(COMPANIES_TABLE).select("시장구분, 산업코드").eq("기업명", company).limit(1).execute()
    static_rows = static_res.data or []
    market = static_rows[0].get("시장구분") if static_rows else None
    industry_code = static_rows[0].get("산업코드") if static_rows else None

    code = fetch_company_code(company)
    asset_row = None
    if code is not None:
        asset_res = (
            sb.table(GRADE_YEARLY_TABLE)
            .select("평가년도, 자산총액, 자산기준군")
            .eq("기업코드", code)
            .order("평가년도", desc=True)
            .limit(1)
            .execute()
        )
        asset_rows = asset_res.data or []
        asset_row = asset_rows[0] if asset_rows else None

    return {
        "market": market,
        "industryCode": industry_code,
        "industryName": INDUSTRY_NAMES.get(industry_code) if industry_code else None,
        "totalAssets": (asset_row or {}).get("자산총액"),
        "assetTier": (asset_row or {}).get("자산기준군"),
    }


def compute_disclosure_roadmap(total_assets: Optional[float]) -> dict[str, Any]:
    """의무공시 적용 시기 — 금융위원회 지속가능성 공시 제도화 방안(최종안), 2026.7 확정 로드맵.
    모든 회사에 동일하게 적용되는 순수 함수다(회사별 분기 없음).

    10조원 이상        → 2028년 시작 (2027 사업연도 기준)
    5조원 이상 10조 미만 → 2029년 시작
    2조원 이상 5조 미만  → 2030년 시작
    2조원 미만          → 적용 대상 아님
    """
    if total_assets is None:
        return {
            "status": "unknown",
            "totalAssets": None,
            "disclosureStartYear": None,
            "deadlineDate": None,
            "scope3GraceYear": None,
        }
    if total_assets >= 10 * ASSET_TRILLION:
        start_year = 2028
    elif total_assets >= 5 * ASSET_TRILLION:
        start_year = 2029
    elif total_assets >= 2 * ASSET_TRILLION:
        start_year = 2030
    else:
        return {
            "status": "not_applicable",
            "totalAssets": total_assets,
            "disclosureStartYear": None,
            "deadlineDate": None,
            "scope3GraceYear": None,
        }
    return {
        "status": "applicable",
        "totalAssets": total_assets,
        "disclosureStartYear": start_year,
        "deadlineDate": f"{start_year - 3}-12-31",  # 3개년 추세 확보를 위한 데이터 축적 착수 기한
        "scope3GraceYear": start_year + 3,  # Scope 3 배출량 공시 유예 종료 연도
    }


def normalize_item(row: dict[str, Any]) -> dict[str, Any]:
    """DB 원본 행 → 화면에서 쓰는 item 요약 구조."""
    bucket = bucket_of(row.get("application_type"), row.get("domain"))
    bucket_meta = DOMAIN_BUCKETS.get(bucket, {"label": row.get("domain") or "기타"})
    score = _to_float(row.get("score"))
    applicable = score is not None
    scoring_type = row.get("scoring_type") or ""
    current_stage = None
    if "단계형" in scoring_type:
        staged = _to_float(row.get("input_satisfied_stage"))
        if staged is not None:
            current_stage = int(staged)
    return {
        "code": row.get("classification_code"),
        "name": row.get("item_name"),
        "category": row.get("category"),
        "domainBucket": bucket,
        "domainLabel": bucket_meta.get("label"),
        "applicationType": row.get("application_type"),
        "scoringType": row.get("scoring_type"),
        "maxStageCount": row.get("max_stage_count"),
        "currentStage": current_stage,
        "score": score,
        "scoreRaw": row.get("score"),
        "max": 100 if applicable else None,  # 항목별 실제 배점 가중치가 원본에 없어 100점 정규화로 통일
        "applicable": applicable,
        "evidence": evidence_level(row.get("note_scoring_model_25")),
        "urgency": row.get("urgency"),
        "solution": row.get("solution"),
        "improvementGuide": row.get("improvement_guide"),
        "dataSource": row.get("data_source"),
    }


def build_domains(items: list[dict[str, Any]], profile: dict[str, Any]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for key, meta in DOMAIN_BUCKETS.items():
        buckets[key] = {
            "key": key,
            "label": meta["label"],
            "items": 0,
            "score": 0.0,
            "max": 0,
            "benchmarkAvg": profile.get("benchmarkAvgByBucket", {}).get(key),
        }
    for it in items:
        b = buckets.get(it["domainBucket"])
        if b is None:
            continue
        b["items"] += 1
        if it["applicable"]:
            b["score"] += it["score"]
            b["max"] += 100
    ordered = sorted(buckets.values(), key=lambda b: DOMAIN_BUCKETS[b["key"]]["order"])
    for b in ordered:
        b["rate"] = round(b["score"] / b["max"], 4) if b["max"] else None
    return ordered


def build_summary(company: str) -> dict[str, Any]:
    profile = get_company_profile(company)
    rows = fetch_rows(company)
    items = [normalize_item(r) for r in rows]
    domains = build_domains(items, profile)

    applicable_items = [it for it in items if it["applicable"]]
    total_score = sum(it["score"] for it in applicable_items)
    total_max = len(applicable_items) * 100

    evidence_counts = {"충분": 0, "부분": 0, "불충분": 0, None: 0}
    for it in items:
        evidence_counts[it["evidence"]] = evidence_counts.get(it["evidence"], 0) + 1

    urgency_counts = {"즉시": 0, "중기": 0, "장기": 0}
    for it in items:
        if it["urgency"] in urgency_counts:
            urgency_counts[it["urgency"]] += 1

    loss_top5 = sorted(
        (it for it in applicable_items),
        key=lambda it: it["score"],
    )[:5]
    loss_top5 = [
        {
            "code": it["code"],
            "name": it["name"],
            "lostPoints": round(100 - it["score"], 1),
            "domainLabel": it["domainLabel"],
        }
        for it in loss_top5
    ]

    immediate = sorted(
        (it for it in applicable_items if it["urgency"] == "즉시"),
        key=lambda it: it["score"],
    )[:5]
    immediate_tasks = [
        {
            "code": it["code"],
            "name": it["name"],
            "domainLabel": it["domainLabel"],
            "currentScore": it["score"],
            "potentialGain": round(100 - it["score"], 1),
            "scoringType": it["scoringType"],
            "solution": it["solution"],
        }
        for it in immediate
    ]
    sim_gain = round(sum(t["potentialGain"] for t in immediate_tasks), 1)

    grade_history = fetch_grade_history(company)
    official_grade = compute_official_grade(grade_history)

    disclosure_roadmap = compute_disclosure_roadmap(fetch_latest_total_assets(company))
    industry_profile = build_industry_profile(company)

    return {
        "company": {
            "name": company,
            "id": profile.get("companyId"),
            "sector": profile.get("sector"),
            "disclosureRoadmap": disclosure_roadmap,
            "disclosureRoadmapCaveat": profile.get("disclosureRoadmapCaveat"),
            "industryProfile": industry_profile,
        },
        "keyIssues": profile.get("keyIssues", []),
        "assessment": {
            "year": ASSESSMENT_YEAR,
            "framework": "K-ESG v2.0",
            "totalScore": round(total_score, 1),
            "maxScore": total_max,
            "rate": round(total_score / total_max, 4) if total_max else None,
            "applicableItems": len(applicable_items),
            "totalItems": len(items),
        },
        "officialGrade": official_grade,
        "gradeHistory": grade_history,
        "domains": domains,
        "evidenceCounts": {
            "충분": evidence_counts.get("충분", 0),
            "부분": evidence_counts.get("부분", 0),
            "불충분": evidence_counts.get("불충분", 0),
            "미평가": evidence_counts.get(None, 0),
        },
        "urgencyCounts": urgency_counts,
        "lossTop5": loss_top5,
        "immediateTasks": immediate_tasks,
        "simulation": {
            "scope": f"즉시 과제 {len(immediate_tasks)}건",
            "from": round(total_score, 1),
            "to": round(total_score + sim_gain, 1),
            "gain": sim_gain,
            "rateFrom": round(total_score / total_max, 4) if total_max else None,
            "rateTo": round((total_score + sim_gain) / total_max, 4) if total_max else None,
            "estimated": True,
        },
        "isMock": profile.get("isMock", False),
    }


def build_domain_detail(company: str, bucket: str) -> dict[str, Any]:
    profile = get_company_profile(company)
    rows = fetch_rows(company)
    items = [normalize_item(r) for r in rows if bucket_of(r.get("application_type"), r.get("domain")) == bucket]

    evidence_counts = {"충분": 0, "부분": 0, "불충분": 0}
    urgency_counts = {"즉시": 0, "중기": 0, "장기": 0}
    scoring_type_counts: dict[str, int] = {}
    for it in items:
        if it["evidence"] in evidence_counts:
            evidence_counts[it["evidence"]] += 1
        if it["urgency"] in urgency_counts:
            urgency_counts[it["urgency"]] += 1
        st = it["scoringType"] or "기타"
        scoring_type_counts[st] = scoring_type_counts.get(st, 0) + 1

    applicable = [it for it in items if it["applicable"]]
    total_score = sum(it["score"] for it in applicable)
    total_max = len(applicable) * 100

    label = DOMAIN_BUCKETS.get(bucket, {"label": bucket}).get("label")

    return {
        "bucket": bucket,
        "label": label,
        "items": items,
        "summary": {
            "itemCount": len(items),
            "score": round(total_score, 1),
            "max": total_max,
            "rate": round(total_score / total_max, 4) if total_max else None,
        },
        "evidenceCounts": evidence_counts,
        "urgencyCounts": urgency_counts,
        "scoringTypeCounts": scoring_type_counts,
        "violations": profile.get("violations", []) if bucket == "environment" else [],
        "isMock": profile.get("isMock", False),
    }


def build_item_detail(company: str, code: str) -> Optional[dict[str, Any]]:
    rows = fetch_rows(company)
    row = next((r for r in rows if r.get("classification_code") == code), None)
    if row is None:
        return None

    base = normalize_item(row)
    note = parse_scoring_note(row.get("note_manual_ai_scoring_26"))
    solution_split = parse_solution(row.get("solution"))

    return {
        **base,
        "itemDescription": row.get("item_description"),
        "dataPeriod": row.get("data_period"),
        "dataScope": row.get("data_scope"),
        "dataFormula": row.get("data_formula"),
        "scoreStructureSummary": row.get("score_structure_summary"),
        "criteriaDetail": row.get("criteria_detail"),
        "kssbStatus": row.get("kssb_status"),
        "kssbReference": row.get("kssb_reference"),
        "otherReferenceStandards": row.get("other_reference_standards"),
        "dueDiligenceQuestion": row.get("due_diligence_question"),
        "answerFormat": row.get("answer_format"),
        "scoringNote": note,
        "solutionSplit": solution_split,
        "pendingReview": get_pending_item(company, code),
        "evidenceSources": extract_evidence_sources(row.get("note_scoring_model_25"), row.get("note_manual_ai_scoring_26")),
    }


def build_report_comparison(company: str) -> Optional[dict[str, Any]]:
    """보고서(docx) 원문 기반 비교 데이터 — L4에서 쓰는 그룹비교·선례·상관도 등. db/report_extracted_data.json이 정답."""
    return get_report_comparison(company)
