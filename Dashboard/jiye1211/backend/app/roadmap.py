"""L5 개선 로드맵 — esg_roadmap_stages/esg_roadmap_tasks/esg_urgency_criteria/esg_disclosure_deadline
(Supabase, 이미 적재되어 있던 값)을 화면이 쓰는 형태로 가공한다.

이 4개 테이블은 컨설팅 보고서 §08 최종 로드맵 원문을 그대로 옮긴 것이며(esg_companies.id로
회사와 연결), 여기서는 표시 형태만 바꾸고 값 자체는 새로 만들어내지 않는다.
"""
from typing import Any, Optional

from .repository import compute_disclosure_roadmap, fetch_latest_total_assets, fetch_rows
from .supabase_client import get_supabase

ESG_COMPANIES_TABLE = "esg_companies"  # 주의: repository.COMPANIES_TABLE("companies")와는 다른 테이블
STAGES_TABLE = "esg_roadmap_stages"
TASKS_TABLE = "esg_roadmap_tasks"
URGENCY_CRITERIA_TABLE = "esg_urgency_criteria"
DISCLOSURE_DEADLINE_TABLE = "esg_disclosure_deadline"

_URGENCY_ORDER = {"즉시": 0, "중기": 1, "장기": 2}

# esg_diagnosis 분류코드 접두어 → L2 도메인 버킷 ("~ 영역 전체" 칩이 이동할 탭).
_LETTER_TO_BUCKET = {"P": "disclosure", "E": "environment", "G": "governance"}


def _fetch_esg_company_id(company: str) -> Optional[int]:
    sb = get_supabase()
    res = sb.table(ESG_COMPANIES_TABLE).select("id").eq("name", company).limit(1).execute()
    rows = res.data or []
    return rows[0]["id"] if rows else None


def _expand_compound_code(raw: str) -> list[str]:
    """"반도체-E-1·E-2·E-4·E-5"처럼 공통 접두어가 첫 조각에만 붙어 있는 압축 표기를 개별 코드로 푼다.
    첫 조각의 "-" 구획 수보다 구획이 적은 뒤쪽 조각에는 첫 조각의 앞쪽 구획을 그대로 붙인다."""
    parts = raw.split("·")
    if len(parts) == 1:
        return parts
    first_segments = parts[0].split("-")
    codes = [parts[0]]
    for part in parts[1:]:
        segments = part.split("-")
        missing = len(first_segments) - len(segments)
        if missing > 0:
            part = "-".join(first_segments[:missing] + segments)
        codes.append(part)
    return codes


def classify_related_codes(raw_codes: list[str]) -> list[dict[str, Any]]:
    """related_item_codes(자유서식) → 화면이 그대로 렌더링할 칩 목록.

    실데이터에 나타나는 4가지 형식만 처리한다:
      - 유효한 단일 항목코드(예: "G-1-3") → type="item" (L3 이동)
      - "비채점과제" → type="non_scoring" (링크 없는 회색 배지)
      - "~전체"(예: "P 영역 전체") → type="domain" (그 도메인의 L2 탭으로 이동)
      - "·"로 묶인 압축 표기(예: "반도체-E-1·E-2·E-4·E-5") → 개별 item 칩 여러 개로 분해
    """
    chips: list[dict[str, Any]] = []
    for raw in raw_codes:
        code = raw.strip()
        if code == "비채점과제":
            chips.append({"type": "non_scoring", "label": "채점 외 과제", "code": None, "bucket": None, "raw": code})
        elif code.endswith("전체"):
            prefix = code.split(" ")[0].split("-")[0]
            bucket = _LETTER_TO_BUCKET.get(prefix)
            chips.append({"type": "domain", "label": code, "code": None, "bucket": bucket, "raw": code})
        elif "·" in code:
            for expanded in _expand_compound_code(code):
                chips.append({"type": "item", "label": expanded, "code": expanded, "bucket": None, "raw": code})
        else:
            chips.append({"type": "item", "label": code, "code": code, "bucket": None, "raw": code})
    return chips


def fetch_urgency_criteria(company: str) -> list[dict[str, Any]]:
    company_id = _fetch_esg_company_id(company)
    if company_id is None:
        return []
    sb = get_supabase()
    res = sb.table(URGENCY_CRITERIA_TABLE).select("level, criteria").eq("company_id", company_id).execute()
    rows = res.data or []
    rows.sort(key=lambda r: _URGENCY_ORDER.get(r.get("level"), 99))
    return [{"level": r["level"], "criteria": r["criteria"]} for r in rows]


def fetch_disclosure_deadline(company: str) -> Optional[dict[str, str]]:
    company_id = _fetch_esg_company_id(company)
    if company_id is None:
        return None
    sb = get_supabase()
    res = sb.table(DISCLOSURE_DEADLINE_TABLE).select("key, value").eq("company_id", company_id).execute()
    rows = res.data or []
    if not rows:
        return None
    return {r["key"]: r["value"] for r in rows}


def build_roadmap(company: str) -> Optional[dict[str, Any]]:
    company_id = _fetch_esg_company_id(company)
    if company_id is None:
        return None

    sb = get_supabase()
    stage_rows = (
        sb.table(STAGES_TABLE)
        .select("stage_no, year, stage_name, urgency_level")
        .eq("company_id", company_id)
        .order("stage_no")
        .execute()
        .data
        or []
    )
    task_rows = (
        sb.table(TASKS_TABLE)
        .select("stage_no, task_name, related_item_codes, deliverables")
        .eq("company_id", company_id)
        .order("stage_no")
        .execute()
        .data
        or []
    )

    # 항목코드 → 시급성(즉시/중기/장기) — esg_diagnosis 채점 데이터 기준 (분포 바 계산용).
    urgency_by_code = {r["classification_code"]: r.get("urgency") for r in fetch_rows(company)}

    tasks_by_stage: dict[int, list[dict[str, Any]]] = {}
    for row in task_rows:
        chips = classify_related_codes(row.get("related_item_codes") or [])
        tasks_by_stage.setdefault(row["stage_no"], []).append(
            {"taskName": row["task_name"], "deliverables": row.get("deliverables"), "chips": chips}
        )

    stages = []
    for row in stage_rows:
        stage_tasks = tasks_by_stage.get(row["stage_no"], [])
        distribution = {"즉시": 0, "중기": 0, "장기": 0}
        for task in stage_tasks:
            for chip in task["chips"]:
                if chip["type"] != "item":
                    continue
                urgency = urgency_by_code.get(chip["code"])
                if urgency in distribution:
                    distribution[urgency] += 1
        stages.append(
            {
                "stageNo": row["stage_no"],
                "year": row["year"],
                "stageName": row["stage_name"],
                "urgencyLevel": row.get("urgency_level"),
                "urgencyDistribution": distribution,
                "tasks": stage_tasks,
            }
        )

    disclosure_roadmap = compute_disclosure_roadmap(fetch_latest_total_assets(company))

    year_mismatch_note = None
    if stages and disclosure_roadmap["status"] == "applicable":
        last_stage_year = stages[-1]["year"]
        start_year = disclosure_roadmap["disclosureStartYear"]
        if last_stage_year != start_year:
            year_mismatch_note = (
                f"로드맵 원문은 {last_stage_year}년을 목표로 설계, 확정 로드맵 기준 실제 적용은 {start_year}년"
            )

    return {
        "stages": stages,
        "urgencyCriteria": fetch_urgency_criteria(company),
        "disclosureDeadline": fetch_disclosure_deadline(company),
        "disclosureRoadmap": disclosure_roadmap,
        "yearMismatchNote": year_mismatch_note,
    }
