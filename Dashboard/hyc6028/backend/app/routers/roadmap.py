from fastapi import APIRouter, HTTPException

from app.schemas_extra import RoadmapResponse, RoiRow, SimulationRequest, SimulationResponse
from app.services import roadmap as roadmap_service

router = APIRouter(prefix="/api/companies", tags=["roadmap"])


@router.get("/{company}/roadmap", response_model=RoadmapResponse)
def get_roadmap(company: str):
    result = roadmap_service.build_roadmap(company)
    if result is None:
        raise HTTPException(status_code=404, detail=f"'{company}'에 대한 진단 데이터가 없습니다")
    return result


@router.get("/{company}/roadmap/roi", response_model=list[RoiRow])
def get_roi(company: str):
    return roadmap_service.build_roi(company)


@router.post("/{company}/simulations", response_model=SimulationResponse)
def post_simulation(company: str, body: SimulationRequest):
    result = roadmap_service.simulate(company, body.task_ids)
    if result is None:
        raise HTTPException(status_code=404, detail=f"'{company}'에 대한 진단 데이터가 없습니다")
    return result
