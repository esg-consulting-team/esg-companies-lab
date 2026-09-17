from fastapi import APIRouter, HTTPException

from app.schemas import DdayInfo
from app.schemas_extra import (
    BenchmarkCompany,
    CompanyProfile,
    RoadmapPlanResponse,
    UrgencyCriteriaResponse,
)
from app.services import enrichment

router = APIRouter(prefix="/api/companies", tags=["enrichment"])


@router.get("/{company}/profile", response_model=CompanyProfile)
def get_profile(company: str):
    result = enrichment.get_company_profile(company)
    if result is None:
        raise HTTPException(status_code=404, detail=f"'{company}'에 등록된 프로필이 없습니다")
    return result


@router.get("/{company}/disclosure-deadline", response_model=DdayInfo)
def get_disclosure_deadline(company: str):
    result = enrichment.compute_dday(company)
    if result is None:
        raise HTTPException(status_code=404, detail=f"'{company}'에 등록된 의무공시 일정 데이터가 없습니다")
    return result


@router.get("/{company}/benchmark-companies", response_model=list[BenchmarkCompany])
def get_benchmark_companies(company: str):
    return enrichment.get_benchmark_companies(company)


@router.get("/{company}/urgency-criteria", response_model=UrgencyCriteriaResponse)
def get_urgency_criteria(company: str):
    return enrichment.get_urgency_criteria(company)


@router.get("/{company}/roadmap-plan", response_model=RoadmapPlanResponse)
def get_roadmap_plan(company: str):
    result = enrichment.get_roadmap_plan(company)
    if result is None:
        raise HTTPException(status_code=404, detail=f"'{company}'에 등록된 로드맵 단계 데이터가 없습니다")
    return result
