"""L6 증빙 데이터룸 — esg_diagnosis 채점 근거 텍스트에서 참고자료 유형을 추출하고,
근거충분성이 낮은 항목을 모은다. 둘 다 기존 esg_diagnosis 컬럼만 쓰고 새 데이터를 만들지 않는다.
"""
import csv
import json
import unicodedata
from pathlib import Path
from typing import Any

from .parsing import evidence_page_text, parse_scoring_note
from .repository import fetch_rows, normalize_item

# (키워드, 표시 라벨) 순서대로 검사 — 한 항목이 여러 키워드에 매칭되면 전부 카운트한다(중복 허용).
_DOC_KEYWORDS: list[tuple[str, str]] = [
    ("사업보고서", "사업보고서"),
    ("지속가능경영보고서", "지속가능경영보고서"),
    ("지배구조보고서", "지배구조보고서"),
    ("통합", "통합 자료"),
]
_UNCLASSIFIED_LABEL = "미분류"


def _evidence_source_text(row: dict[str, Any]) -> str:
    page_text = evidence_page_text(row.get("note_scoring_model_25")) or ""
    confirmed_basis = parse_scoring_note(row.get("note_manual_ai_scoring_26")).get("confirmedBasis") or ""
    return f"{page_text} {confirmed_basis}"


def build_document_coverage(company: str) -> dict[str, Any]:
    """Exhibit 1 — 참고자료 유형별 연결 항목 수(근사치, 키워드 매칭 기반).

    score가 "N/A(업종 미해당)"처럼 숫자로 변환되지 않는 행(= normalize_item의 applicable=False,
    "해당 없음")은 애초에 채점 자체가 없어 근거문서를 논할 대상이 아니므로, 분모(전체 항목 수)와
    "미분류" 집계 양쪽에서 완전히 제외한다 — L1/L2가 이미 applicable로 걸러 쓰는 것과 동일한 기준.
    """
    applicable_rows = [r for r in fetch_rows(company) if normalize_item(r)["applicable"]]
    counts: dict[str, int] = {label: 0 for _, label in _DOC_KEYWORDS}
    counts[_UNCLASSIFIED_LABEL] = 0
    unclassified = 0

    for row in applicable_rows:
        text = _evidence_source_text(row)
        matched = False
        for keyword, label in _DOC_KEYWORDS:
            if keyword in text:
                counts[label] += 1
                matched = True
        if not matched:
            counts[_UNCLASSIFIED_LABEL] += 1
            unclassified += 1

    total = len(applicable_rows)
    return {
        "documentCounts": [{"label": label, "count": counts[label]} for _, label in _DOC_KEYWORDS]
        + [{"label": _UNCLASSIFIED_LABEL, "count": counts[_UNCLASSIFIED_LABEL]}],
        "totalItems": total,
        "unclassifiedCount": unclassified,
        "unclassifiedRate": round(unclassified / total, 4) if total else None,
    }


def build_evidence_gaps(company: str) -> list[dict[str, Any]]:
    """Exhibit 2 — 근거충분성이 불충분/부분인 항목 목록. evidence_level()을 그대로 재사용한다."""
    items = [normalize_item(r) for r in fetch_rows(company)]
    gaps = [it for it in items if it["evidence"] in ("불충분", "부분")]
    gaps.sort(key=lambda it: (it["score"] if it["score"] is not None else 0))
    return [
        {
            "code": it["code"],
            "name": it["name"],
            "evidence": it["evidence"],
            "lostPoints": round(100 - it["score"], 1) if it["applicable"] else None,
        }
        for it in gaps
    ]


# ── Exhibit 3 — 문서 인벤토리 (db/manifest.csv · extraction_diagnostics.csv · checkpoint_completed.json) ──
_DB_DIR = Path(__file__).resolve().parents[2] / "db"
# manifest의 doc_type → 위 Exhibit 1과 같은 표시 라벨 (연결 항목 수는 build_document_coverage 결과를 그대로 재사용)
_DOC_TYPE_LABELS = {
    "business_report": "사업보고서",
    "sustainability_report": "지속가능경영보고서",
    "governance_report": "지배구조보고서",
}


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text or "")


def _read_csv(name: str) -> list[dict[str, str]]:
    with open(_DB_DIR / name, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _failed_page_count(raw: str) -> int:
    raw = (raw or "").strip()
    if not raw or raw == "[]":
        return 0
    return len([p for p in raw.strip("[]").split(",") if p.strip()])


def build_document_inventory(company: str) -> list[dict[str, Any]]:
    """회사별 문서 목록. 페이지 수·추출 실패 페이지 수는 extraction_diagnostics.csv, 완료 여부는
    checkpoint_completed.json에 doc_id가 있는지로만 판정한다(완료/미완료 2단계 — 그 외 상태는 추적 근거 없음).
    연결 항목 수는 build_document_coverage의 문서유형별 키워드 매칭 결과를 그대로 재사용한다."""
    manifest = [r for r in _read_csv("manifest.csv") if _nfc(r["company_name"]) == company]
    diagnostics = {r["doc_id"]: r for r in _read_csv("extraction_diagnostics.csv")}
    with open(_DB_DIR / "checkpoint_completed.json", encoding="utf-8") as f:
        completed = set(json.load(f))
    linked = {d["label"]: d["count"] for d in build_document_coverage(company)["documentCounts"]}

    rows = []
    for r in manifest:
        doc_id = f"{r['company_code']}_{r['year']}_{r['doc_type']}"
        diag = diagnostics.get(doc_id)
        label = _DOC_TYPE_LABELS.get(r["doc_type"], r["doc_type"])
        rows.append(
            {
                "docId": doc_id,
                "docType": label,
                "year": int(r["year"]),
                "totalPages": int(diag["total_pages"]) if diag and diag.get("total_pages") else None,
                "failedPages": _failed_page_count(diag.get("still_failed_pages")) if diag else None,
                "parsed": doc_id in completed,
                "linkedItems": linked.get(label),
            }
        )
    rows.sort(key=lambda x: (x["docType"], x["year"]))
    return rows
