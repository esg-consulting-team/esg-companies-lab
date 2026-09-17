import io

from openpyxl import Workbook
from openpyxl.styles import Font

from app.db import get_supabase
from app.schemas_extra import ExportRecord, ReportConfigResponse, ReportSection
from app.services import diagnosis

REPORT_SECTIONS = [
    ReportSection(no="01", title="컨설팅 배경", pages=2),
    ReportSection(no="02", title="고객사 리서치", pages=2),
    ReportSection(no="03", title="벤치마킹사 소개", pages=1),
    ReportSection(no="04", title="ESG 등급 산출표", pages=2),
    ReportSection(no="05", title="고객사 문제인식", pages=3),
    ReportSection(no="06", title="개선 과제", pages=5),
    ReportSection(no="부록", title="항목별 채점근거 전체", pages=18),
]

EXPORT_COLUMNS = [
    ("category_code", "분류코드"),
    ("domain", "영역"),
    ("category", "범주"),
    ("item_name", "진단항목명"),
    ("score", "자사취득점수"),
    ("urgency", "시급성"),
    ("scoring_type", "채점유형"),
    ("kssb_status", "KSSB 대응현황"),
    ("solution", "해결방안"),
]


def get_report_config(company: str) -> ReportConfigResponse | None:
    items = diagnosis.fetch_items(company)
    if not items:
        return None
    supabase = get_supabase()
    hist_res = (
        supabase.table("report_exports")
        .select("*")
        .eq("company", company)
        .order("created_at", desc=True)
        .limit(10)
        .execute()
    )
    history = [
        ExportRecord(
            format=r["format"],
            sections=r["sections"],
            page_estimate=r.get("page_estimate"),
            created_at=r["created_at"],
        )
        for r in (hist_res.data or [])
    ]
    return ReportConfigResponse(sections=REPORT_SECTIONS, export_history=history)


def build_xlsx(company: str) -> bytes:
    items = diagnosis.fetch_items(company)
    wb = Workbook()
    ws = wb.active
    ws.title = "ESG 진단 결과"
    headers = [label for _, label in EXPORT_COLUMNS]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for r in items:
        ws.append([r.get(key) for key, _ in EXPORT_COLUMNS])
    for col in ws.columns:
        width = max((len(str(c.value)) for c in col if c.value is not None), default=10)
        ws.column_dimensions[col[0].column_letter].width = min(max(width + 2, 10), 60)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def log_export(company: str, fmt: str, section_nos: list[str]) -> None:
    supabase = get_supabase()
    total_pages = sum(s.pages for s in REPORT_SECTIONS if s.no in section_nos)
    supabase.table("report_exports").insert(
        {
            "company": company,
            "format": fmt,
            "sections": section_nos,
            "page_estimate": total_pages,
        }
    ).execute()
