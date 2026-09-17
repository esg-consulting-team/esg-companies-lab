from fastapi import APIRouter, HTTPException

from app.schemas_extra import DocumentRoomResponse
from app.services import documents as documents_service

router = APIRouter(prefix="/api/companies", tags=["documents"])


@router.get("/{company}/documents", response_model=DocumentRoomResponse)
def get_documents(company: str):
    result = documents_service.build_document_room(company)
    if result is None:
        raise HTTPException(status_code=404, detail=f"'{company}'에 대한 진단 데이터가 없습니다")
    return result
