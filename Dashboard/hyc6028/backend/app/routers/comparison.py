from fastapi import APIRouter, HTTPException

from app.schemas_extra import ComparisonResponse
from app.services import comparison

router = APIRouter(prefix="/api/companies", tags=["comparison"])


@router.get("/{company}/comparison", response_model=ComparisonResponse)
def get_comparison(company: str):
    result = comparison.build_comparison(company)
    if result is None:
        raise HTTPException(status_code=404, detail=f"'{company}'에 대한 진단 데이터가 없습니다")
    return result
