from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Response

from app.schemas_extra import ExportRequest, ReportConfigResponse
from app.services import reports as reports_service

router = APIRouter(prefix="/api/companies", tags=["reports"])


@router.get("/{company}/report/config", response_model=ReportConfigResponse)
def get_report_config(company: str):
    result = reports_service.get_report_config(company)
    if result is None:
        raise HTTPException(status_code=404, detail=f"'{company}'에 대한 진단 데이터가 없습니다")
    return result


@router.post("/{company}/report/export")
def export_report(company: str, body: ExportRequest):
    if body.format == "xlsx":
        content = reports_service.build_xlsx(company)
        reports_service.log_export(company, body.format, body.section_nos)
        filename_utf8 = quote(f"{company}_esg_export.xlsx")
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename=\"esg_export.xlsx\"; filename*=UTF-8''{filename_utf8}"
            },
        )
    raise HTTPException(
        status_code=501,
        detail=f"{body.format.upper()} 내보내기는 확장 단계(F6-04)에서 제공될 예정입니다. 현재는 XLSX만 지원합니다.",
    )
