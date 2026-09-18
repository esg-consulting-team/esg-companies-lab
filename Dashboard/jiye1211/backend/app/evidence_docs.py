"""L6 증빙 데이터룸 — esg_diagnosis 채점 근거 텍스트에서 참고자료 유형을 추출하고,
근거충분성이 낮은 항목을 모은다. 둘 다 기존 esg_diagnosis 컬럼만 쓰고 새 데이터를 만들지 않는다.
"""
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
