"""컨설팅 보고서(docx) 원문에서 사람이 직접 검증한 구조화 데이터.

원본: db/report_extracted_data.json — 두 보고서를 재파싱하지 않고 이 파일을 정답 데이터로 쓴다
(README의 "_readme" 참고). null 값은 보고서에 아예 없는 값이므로 프론트엔드가 임의로 채우지 않고
"해당 데이터 없음"으로 표시한다.
"""
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

_JSON_PATH = Path(__file__).resolve().parents[2] / "db" / "report_extracted_data.json"

# JSON의 회사 키 → 앱 전체에서 쓰는 회사명(esg_diagnosis.company 값)
_COMPANY_KEY_MAP = {
    "DN오토모티브": "007340_DN오토모티브",
    "하나마이크론": "하나마이크론_ESG반도체특화",
}

# report_extracted_data.json domainScores의 도메인명(보고서 원문 표기) → DOMAIN_BUCKETS 키.
# "반도체특화"/"업종특화"는 보고서마다 표기가 다를 뿐 같은 버킷(sector)이다.
_DOMAIN_LABEL_TO_BUCKET = {
    "정보공시": "disclosure",
    "환경": "environment",
    "지배구조": "governance",
    "업종특화": "sector",
    "반도체특화": "sector",
}


@lru_cache(maxsize=1)
def _load() -> dict[str, Any]:
    with _JSON_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def get_report_comparison(company: str) -> Optional[dict[str, Any]]:
    """회사의 보고서 기반 비교 데이터(그룹비교·선례·상관도 등)를 JSON 원본 그대로 반환한다."""
    key = _COMPANY_KEY_MAP.get(company)
    if key is None:
        return None
    return _load().get("companies", {}).get(key)


def get_domain_benchmark_map(company: str) -> dict[str, float]:
    """L1 Exhibit1용 도메인별 벤치마킹 평균(0~1 비율) — 컨설팅 보고서가 domainScores를 실제로
    검증해 둔 회사(현재는 하나마이크론)만 반환한다. 없으면 빈 dict — 호출부가 mock_data.py의
    참고용 샘플값으로 대체한다."""
    data = get_report_comparison(company)
    if not data or "domainScores" not in data:
        return {}
    result: dict[str, float] = {}
    for row in data["domainScores"]:
        bucket = _DOMAIN_LABEL_TO_BUCKET.get(row.get("domain"))
        avg = row.get("benchmarkAvg")
        if bucket and avg is not None:
            result[bucket] = avg / 100
    return result


def get_pending_item(company: str, item_code: str) -> Optional[dict[str, Any]]:
    """항목코드에 해당하는 '판정 확인 중' 항목이 있으면 반환한다."""
    data = get_report_comparison(company)
    if not data:
        return None
    for entry in data.get("pendingItems", []):
        if entry.get("itemCode") == item_code:
            return entry
    return None
