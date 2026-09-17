from fastapi import APIRouter, HTTPException

from app.schemas import ItemDetail
from app.services import diagnosis

router = APIRouter(prefix="/api/companies", tags=["items"])


@router.get("/{company}/items/{item_code}", response_model=ItemDetail)
def get_item_detail(company: str, item_code: str):
    result = diagnosis.build_item_detail(company, item_code)
    if result is None:
        raise HTTPException(status_code=404, detail="해당 항목을 찾을 수 없습니다")
    return result
