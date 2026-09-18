"""Gemini function calling으로 호출되는 Supabase/보고서 정형 데이터 조회 함수.

문서 유사도 검색(rag.search_documents)만으로는 답할 수 없는 질문 — 종합점수·등급, 항목별
채점근거+서술형 평가, 시급성별 과제, 로드맵 단계별 시급성 분포, 보고서 고유 인사이트, 벤치마킹
대상 회사명 — 에 한해 Gemini가 스스로 아래 함수 중 필요한 것을 골라 호출한다(질문에 소주제가
여러 개면 여러 함수를 함께 호출할 수 있다. rag._route_calls/_resolve_structured_call 참고).

여기 함수들은 순수 데이터 조회만 한다(LLM 호출 없음) — 여러 함수의 조회 결과를 문서 검색
결과와 함께 종합해 자연어 답변으로 바꾸는 작업은 rag._answer가 한다.

Supabase 테이블·컬럼명은 항상 backend/schema_config.py의 TABLE_MAP을 통해서만 참조한다.
"""
from typing import Any, Optional

from schema_config import TABLE_MAP

from .report_data import get_report_comparison
from .repository import fetch_domain_benchmark
from .roadmap import classify_related_codes
from .supabase_client import get_supabase


def _company_name(company_code: str) -> Optional[str]:
    """companies.기업코드 → 기업명 (esg_diagnosis.company 텍스트 매칭에 쓸 이름)."""
    cfg = TABLE_MAP["companies_legacy"]
    sb = get_supabase()
    res = sb.table(cfg["table"]).select(cfg["name_col"]).eq(cfg["code_col"], company_code).limit(1).execute()
    rows = res.data or []
    return rows[0][cfg["name_col"]] if rows else None


def _esg_company_id(company_code: str) -> Optional[int]:
    """esg_companies.stock_code → id (esg_item_narrative/esg_roadmap_* 조회에 필요)."""
    cfg = TABLE_MAP["esg_companies"]
    sb = get_supabase()
    res = sb.table(cfg["table"]).select(cfg["id_col"]).eq(cfg["stock_code_col"], company_code).limit(1).execute()
    rows = res.data or []
    return rows[0][cfg["id_col"]] if rows else None


def get_company_summary(company_code: str) -> dict[str, Any]:
    """company_esg_yearly에서 이 회사의 최신 연도 종합점수·등급(종합/E/S/G)·반도체제외 점수를 가져온다."""
    cfg = TABLE_MAP["company_score_yearly"]
    sb = get_supabase()
    select_cols = ", ".join(
        [
            cfg["year_col"],
            cfg["grade_overall_col"],
            cfg["grade_e_col"],
            cfg["grade_s_col"],
            cfg["grade_g_col"],
            cfg["score_avg_col"],
            cfg["score_disclosure_col"],
            cfg["score_env_col"],
            cfg["score_gov_col"],
            cfg["score_avg_excl_semi_col"],
            cfg["score_disclosure_excl_semi_col"],
            cfg["score_env_excl_semi_col"],
            cfg["score_gov_excl_semi_col"],
        ]
    )
    res = (
        sb.table(cfg["table"])
        .select(select_cols)
        .eq(cfg["company_key_col"], company_code)
        .order(cfg["year_col"], desc=True)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    if not rows:
        return {"found": False, "reason": f"'{company_code}'의 연도별 채점 데이터가 없습니다."}

    row = rows[0]
    return {
        "found": True,
        "companyCode": company_code,
        "year": row.get(cfg["year_col"]),
        "grade": {
            "overall": row.get(cfg["grade_overall_col"]),
            "environment": row.get(cfg["grade_e_col"]),
            "social": row.get(cfg["grade_s_col"]),
            "governance": row.get(cfg["grade_g_col"]),
        },
        "score": {
            "overall": row.get(cfg["score_avg_col"]),
            "disclosure": row.get(cfg["score_disclosure_col"]),
            "environment": row.get(cfg["score_env_col"]),
            "governance": row.get(cfg["score_gov_col"]),
        },
        "scoreExcludingSemiconductor": {
            "overall": row.get(cfg["score_avg_excl_semi_col"]),
            "disclosure": row.get(cfg["score_disclosure_excl_semi_col"]),
            "environment": row.get(cfg["score_env_excl_semi_col"]),
            "governance": row.get(cfg["score_gov_excl_semi_col"]),
        },
    }


def get_item_detail(item_code: str, company_code: str) -> dict[str, Any]:
    """esg_diagnosis(채점 데이터, company 텍스트 매칭) + esg_item_narrative(서술형 평가,
    company_id는 esg_companies.stock_code로 먼저 찾는다) 를 합쳐서 반환한다."""
    company_name = _company_name(company_code)
    if company_name is None:
        return {"found": False, "reason": f"'{company_code}'에 해당하는 회사를 찾을 수 없습니다."}

    diag_cfg = TABLE_MAP["diagnosis"]
    sb = get_supabase()
    diag_rows = (
        sb.table(diag_cfg["table"])
        .select("*")
        .eq(diag_cfg["company_match_col"], company_name)
        .eq(diag_cfg["item_code_col"], item_code)
        .limit(1)
        .execute()
        .data
        or []
    )
    diagnosis = diag_rows[0] if diag_rows else None

    narrative = None
    company_id = _esg_company_id(company_code)
    if company_id is not None:
        nar_cfg = TABLE_MAP["item_narrative"]
        nar_rows = (
            sb.table(nar_cfg["table"])
            .select("*")
            .eq(nar_cfg["company_id_col"], company_id)
            .eq(nar_cfg["item_code_col"], item_code)
            .limit(1)
            .execute()
            .data
            or []
        )
        narrative = nar_rows[0] if nar_rows else None

    if diagnosis is None and narrative is None:
        return {"found": False, "reason": f"'{item_code}' 항목 데이터를 찾을 수 없습니다."}

    result: dict[str, Any] = {"found": True, "itemCode": item_code, "company": company_name}
    if diagnosis:
        result["diagnosis"] = {
            "itemName": diagnosis.get(diag_cfg["item_name_col"]),
            "domain": diagnosis.get(diag_cfg["domain_col"]),
            "score": diagnosis.get(diag_cfg["score_col"]),
            "urgency": diagnosis.get(diag_cfg["urgency_col"]),
            "solution": diagnosis.get(diag_cfg["solution_col"]),
            "criteriaDetail": diagnosis.get(diag_cfg["criteria_col"]),
            "kssbStatus": diagnosis.get(diag_cfg["kssb_status_col"]),
        }
    if narrative:
        result["narrative"] = {
            "itemName": narrative.get(nar_cfg["item_name_col"]),
            "fulfilledLevelText": narrative.get(nar_cfg["fulfilled_level_col"]),
            "status": narrative.get(nar_cfg["status_col"]),
            "improvement": narrative.get(nar_cfg["improvement_col"]),
            "followup": narrative.get(nar_cfg["followup_col"]),
            "benchmarkCase": narrative.get(nar_cfg["benchmark_case_col"]),
        }
    return result


def get_items_by_urgency(company_code: str, urgency_level: str, full: bool = False) -> dict[str, Any]:
    """esg_diagnosis를 urgency로 필터링한다.

    full=False(기본, "몇 개야"류 단순 질문): 개수 + 대표 5개(도메인·점수 포함).
    full=True("다 뭐야"/"목록"/"전부"류 전체 요청): 전체 항목을 코드+이름만으로 반환한다
    (해결방안 등 상세는 get_item_detail에서 따로 조회하면 되므로 여기서는 목록 용도로만 가볍게 준다).
    """
    company_name = _company_name(company_code)
    if company_name is None:
        return {"found": False, "reason": f"'{company_code}'에 해당하는 회사를 찾을 수 없습니다."}

    cfg = TABLE_MAP["diagnosis"]
    sb = get_supabase()
    rows = (
        sb.table(cfg["table"])
        .select("*")
        .eq(cfg["company_match_col"], company_name)
        .eq(cfg["urgency_col"], urgency_level)
        .execute()
        .data
        or []
    )

    if full:
        items = [
            {"itemCode": r.get(cfg["item_code_col"]), "itemName": r.get(cfg["item_name_col"])} for r in rows
        ]
    else:
        items = [
            {
                "itemCode": r.get(cfg["item_code_col"]),
                "itemName": r.get(cfg["item_name_col"]),
                "domain": r.get(cfg["domain_col"]),
                "score": r.get(cfg["score_col"]),
            }
            for r in rows
        ][:5]

    return {
        "found": True,
        "company": company_name,
        "urgencyLevel": urgency_level,
        "scope": "full" if full else "summary",
        "count": len(rows),
        "items": items,
    }


def get_roadmap_urgency_distribution(stage_no: int, company_code: str) -> dict[str, Any]:
    """esg_roadmap_tasks.related_item_codes(배열)로 esg_diagnosis를 조인해 이 단계 과제들의
    관련 항목을 즉시/중기/장기로 집계한다 (로드맵 화면의 단계 배지가 뭉개지는 문제 대응용)."""
    company_id = _esg_company_id(company_code)
    if company_id is None:
        return {"found": False, "reason": f"'{company_code}'의 로드맵 데이터를 찾을 수 없습니다."}

    tasks_cfg = TABLE_MAP["roadmap_tasks"]
    sb = get_supabase()
    task_rows = (
        sb.table(tasks_cfg["table"])
        .select("*")
        .eq(tasks_cfg["company_id_col"], company_id)
        .eq(tasks_cfg["stage_no_col"], stage_no)
        .execute()
        .data
        or []
    )
    if not task_rows:
        return {"found": False, "reason": f"{stage_no}단계에 등록된 로드맵 과제가 없습니다."}

    urgency_by_code: dict[str, Optional[str]] = {}
    company_name = _company_name(company_code)
    if company_name is not None:
        diag_cfg = TABLE_MAP["diagnosis"]
        diag_rows = (
            sb.table(diag_cfg["table"])
            .select(f"{diag_cfg['item_code_col']}, {diag_cfg['urgency_col']}")
            .eq(diag_cfg["company_match_col"], company_name)
            .execute()
            .data
            or []
        )
        urgency_by_code = {r[diag_cfg["item_code_col"]]: r.get(diag_cfg["urgency_col"]) for r in diag_rows}

    distribution = {"즉시": 0, "중기": 0, "장기": 0}
    task_names = []
    for row in task_rows:
        task_names.append(row.get(tasks_cfg["task_name_col"]))
        raw_codes = row.get(tasks_cfg["related_item_codes_col"]) or []
        for chip in classify_related_codes(raw_codes):
            if chip["type"] != "item":
                continue
            urgency = urgency_by_code.get(chip["code"])
            if urgency in distribution:
                distribution[urgency] += 1

    return {
        "found": True,
        "companyCode": company_code,
        "stageNo": stage_no,
        "taskCount": len(task_rows),
        "taskNames": task_names,
        "urgencyDistribution": distribution,
    }


def get_report_insight(company_code: str, topic: str) -> dict[str, Any]:
    """db/report_extracted_data.json(schema_config.STATIC_REFERENCE_FILE, 컨설팅 보고서 원문
    추출본)에서 topic에 맞는 항목을 그대로 반환한다.

    파일 자체는 report_data.py가 이미 로드·캐시하고 있고(회사명 → JSON 키 매핑까지 포함),
    이 매핑을 여기서 다시 구현하면 두 곳의 결과가 어긋날 수 있어 그 로더를 그대로 재사용한다.
    """
    company_name = _company_name(company_code)
    if company_name is None:
        return {"found": False, "reason": f"'{company_code}'에 해당하는 회사를 찾을 수 없습니다."}

    data = get_report_comparison(company_name)
    if data is None:
        return {"found": False, "reason": f"'{company_name}'에 대한 보고서 추출 데이터가 없습니다."}

    value = data.get(topic)
    if value is None:
        return {
            "found": False,
            "reason": f"'{topic}' 항목은 보고서 추출 데이터에 없습니다.",
            "availableTopics": [k for k in data.keys() if not k.startswith("note_")],
        }
    return {"found": True, "company": company_name, "topic": topic, "value": value}


def get_benchmark_peer_names(company_code: str) -> dict[str, Any]:
    """이 회사의 벤치마킹 대상 회사 실명 목록을 반환한다.

    새로 조회 로직을 짜지 않고 L4 "자사 vs 벤치마킹군" 화면이 이미 쓰고 있는
    repository.fetch_domain_benchmark를 그대로 재사용한다 — 이 함수가
    benchmark_config.BENCHMARK_MAP(회사별 벤치마킹 실명 목록)으로 피어를 정하고
    company_esg_yearly에서 각 피어의 최신 점수가 있는지까지 확인해 주므로, 실제로
    화면에 표시되는 것과 항상 같은 목록이 나온다.

    (참고: esg_benchmark_companies/esg_kcgs_grades 테이블에도 벤치마킹 데이터가 있지만
    "벤치마킹사 A/B/C(/D)"로 익명화돼 있고 어떤 화면·코드에서도 참조되지 않는 죽은 데이터다.
    업종분류·등급 추이를 대조해 보면 BENCHMARK_MAP과 동일한 회사 집합을 가리키는 것으로
    확인됐다 — 즉 서로 다른 벤치마킹 세트가 아니라 같은 데이터의 익명/실명 버전이며,
    챗봇은 화면에도 쓰이는 실명 버전(BENCHMARK_MAP 경유)만 쓴다.)
    """
    company_name = _company_name(company_code)
    if company_name is None:
        return {"found": False, "reason": f"'{company_code}'에 해당하는 회사를 찾을 수 없습니다."}

    benchmark = fetch_domain_benchmark(company_name)
    peer_names = [p["company"] for p in benchmark.get("peers", []) if p.get("company")]
    if not peer_names:
        return {"found": False, "reason": f"'{company_name}'에 등록된 벤치마킹 대상 회사가 없습니다."}

    return {
        "found": True,
        "company": company_name,
        "peerCompanies": peer_names,
        "peerCount": len(peer_names),
    }
