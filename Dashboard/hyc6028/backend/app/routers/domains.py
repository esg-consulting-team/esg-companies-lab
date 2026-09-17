from fastapi import APIRouter, HTTPException

from app.schemas import DomainItemsResponse
from app.services import diagnosis

router = APIRouter(prefix="/api/companies", tags=["domains"])


@router.get("/{company}/domains/{domain_key}/items", response_model=DomainItemsResponse)
def get_domain_items(company: str, domain_key: str):
    result = diagnosis.build_domain_items(company, domain_key)
    if result is None:
        raise HTTPException(status_code=404, detail="해당 영역 데이터를 찾을 수 없습니다")
    return result
