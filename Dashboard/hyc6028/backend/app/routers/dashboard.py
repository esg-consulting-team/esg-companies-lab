from fastapi import APIRouter, HTTPException

from app.schemas import DashboardSummary
from app.services import diagnosis

router = APIRouter(prefix="/api/companies", tags=["dashboard"])


@router.get("/{company}/summary", response_model=DashboardSummary)
def get_summary(company: str):
    summary = diagnosis.build_dashboard_summary(company)
    if summary is None:
        raise HTTPException(status_code=404, detail=f"'{company}'에 대한 진단 데이터가 없습니다")
    return summary
