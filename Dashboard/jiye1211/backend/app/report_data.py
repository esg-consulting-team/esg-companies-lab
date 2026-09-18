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


def get_pending_item(company: str, item_code: str) -> Optional[dict[str, Any]]:
    """항목코드에 해당하는 '판정 확인 중' 항목이 있으면 반환한다."""
    data = get_report_comparison(company)
    if not data:
        return None
    for entry in data.get("pendingItems", []):
        if entry.get("itemCode") == item_code:
            return entry
    return None
