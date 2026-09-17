from app.db import get_supabase
from app.schemas_extra import DataGapRow, DocumentRoomResponse, DocumentRow
from app.services import diagnosis


def build_document_room(company: str) -> DocumentRoomResponse | None:
    items = diagnosis.fetch_items(company)
    if not items:
        return None

    supabase = get_supabase()
    doc_res = supabase.table("documents").select("*").eq("company", company).order("id").execute()
    documents = [
        DocumentRow(
            name=r["name"],
            doc_type=r.get("doc_type"),
            year=r.get("year"),
            size_label=r.get("size_label"),
            parse_status=r["parse_status"],
            linked_items=r.get("linked_items", 0),
        )
        for r in (doc_res.data or [])
    ]

    data_gaps = []
    for r in items:
        if r.get("score") is None:
            continue
        ev = diagnosis.parse_evidence(r.get("note_scoring_model"))
        if ev.evidence_sufficiency not in ("불충분", "부분", "부분적"):
            continue
        sol = diagnosis.parse_solution(r.get("solution"))
        if not sol.required_evidence:
            continue
        data_gaps.append(
            DataGapRow(
                item_code=r["category_code"],
                item_name=r["item_name"],
                evidence_sufficiency=ev.evidence_sufficiency,
                required_evidence=sol.required_evidence[:300],
            )
        )
    data_gaps.sort(key=lambda g: 0 if g.evidence_sufficiency == "불충분" else 1)

    return DocumentRoomResponse(documents=documents, data_gaps=data_gaps[:10])
