from fastapi import APIRouter

from app.schemas import CompanyMeta
from app.services import diagnosis

router = APIRouter(prefix="/api/companies", tags=["companies"])


@router.get("", response_model=list[CompanyMeta])
def get_companies():
    return diagnosis.list_companies()
