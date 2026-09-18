"""L7 리포트 표지 — esg_company_profile(Supabase) 원본 필드를 그대로 반환한다.
계산·가공 로직 없음(필드명만 camelCase로 옮긴다)."""
from typing import Any, Optional

from .supabase_client import get_supabase

ESG_COMPANIES_TABLE = "esg_companies"  # 주의: repository.COMPANIES_TABLE("companies")와는 다른 테이블
ESG_COMPANY_PROFILE_TABLE = "esg_company_profile"


def _fetch_esg_company_id(company: str) -> Optional[int]:
    sb = get_supabase()
    res = sb.table(ESG_COMPANIES_TABLE).select("id").eq("name", company).limit(1).execute()
    rows = res.data or []
    return rows[0]["id"] if rows else None


def fetch_company_profile_card(company: str) -> Optional[dict[str, Any]]:
    company_id = _fetch_esg_company_id(company)
    if company_id is None:
        return None
    sb = get_supabase()
    res = (
        sb.table(ESG_COMPANY_PROFILE_TABLE)
        .select("stock_code, 설립연도, 상장구분, 주요사업, 연결자산총액, 업종분류, 종업원수")
        .eq("company_id", company_id)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    if not rows:
        return None
    r = rows[0]
    return {
        "stockCode": r.get("stock_code"),
        "establishedYear": r.get("설립연도"),
        "listingType": r.get("상장구분"),
        "mainBusiness": r.get("주요사업"),
        "consolidatedAssets": r.get("연결자산총액"),
        "industryClassification": r.get("업종분류"),
        "employeeCount": r.get("종업원수"),
    }
