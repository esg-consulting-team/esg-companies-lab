"""esg_diagnosis 테이블의 자유서식 텍스트 컬럼에서 구조화된 정보를 뽑아내는 유틸리티.

원본 엑셀은 컨설턴트가 셀에 자유롭게 적어 넣은 메모라 회사(DN오토모티브 / 하나마이크론)마다
서식이 다르다. 여기서는 "최대한 구조화하되, 못 찾으면 원문을 그대로 보여준다"는 원칙으로 만든다.
"""
import re
from typing import Optional, TypedDict

# ── 영역(도메인) 버킷 ──────────────────────────────────────────────
# 사양서(§03 Exhibit1)의 4개 버킷과 1:1 매핑. 실제 DB의 application_type/domain 조합으로 판별한다.
DOMAIN_BUCKETS: dict[str, dict[str, str]] = {
    "disclosure": {"label": "정보공시", "order": "0"},
    "environment": {"label": "환경 E", "order": "1"},
    "governance": {"label": "지배구조 G", "order": "2"},
    "sector": {"label": "업종특화", "order": "3"},
}


def bucket_of(application_type: Optional[str], domain: Optional[str]) -> str:
    if application_type and application_type.startswith("업종특화"):
        return "sector"
    if domain == "정보공시":
        return "disclosure"
    if domain == "환경":
        return "environment"
    if domain == "지배구조":
        return "governance"
    return "other"


# ── 근거충분성 ──────────────────────────────────────────────────────
# note_scoring_model_25 컬럼은 "[자동채점] | 근거충분성: 충분 | 근거: ... | 근거페이지: ..." 형식을
# 대체로 따른다(84행 중 77행 매칭 확인). 못 찾으면 None을 반환하고 프론트에서 "평가 예정"으로 표기한다.
_EVIDENCE_RE = re.compile(r"근거충분성\s*:\s*([^|]+)")


def evidence_level(note_scoring_model_25: Optional[str]) -> Optional[str]:
    if not note_scoring_model_25:
        return None
    m = _EVIDENCE_RE.search(note_scoring_model_25)
    if not m:
        return None
    raw = m.group(1).strip()
    if "불충분" in raw:
        return "불충분"
    if "부분" in raw:
        return "부분"
    if "충분" in raw:
        return "충분"
    return None


# "근거페이지:" 이후 텍스트 — L6 참고자료 유형 추출(텍스트 마이닝)에 쓴다.
_EVIDENCE_PAGE_RE = re.compile(r"근거페이지\s*:\s*(.+)$", re.S)


def evidence_page_text(note_scoring_model_25: Optional[str]) -> Optional[str]:
    if not note_scoring_model_25:
        return None
    m = _EVIDENCE_PAGE_RE.search(note_scoring_model_25)
    return m.group(1).strip() if m else None


# ── "문서명 + 페이지" 추출 — L3 "출처" 캡션 전용 ────────────────────
# 두 표기를 모두 인식한다: "문서명 숫자p"(역순, 근거페이지: 필드에 다수) /
# "문서명 p.숫자"([확인근거] 자유서술에 소수). 페이지 범위("25~28p")도 그대로 살린다.
_DOC_PAGE_REVERSED_RE = re.compile(r"([가-힣A-Za-z][가-힣A-Za-z0-9]*)\s*(\d+(?:[~\-]\d+)?p)\b")
_DOC_PAGE_DOTTED_RE = re.compile(r"([가-힣A-Za-z][가-힣A-Za-z0-9_]*)\s*p\.\s?(\d+(?:[~\-]\d+)?)")


def extract_evidence_sources(note_scoring_model_25: Optional[str], note_manual_ai_scoring_26: Optional[str]) -> list[str]:
    """L3 "출처: 문서명 p.페이지" 캡션용 목록을 만든다.

    note_scoring_model_25의 "근거페이지:" 텍스트를 우선 쓰고(84건 중 77건이 여기서 걸림),
    거기서 못 찾으면 note_manual_ai_scoring_26의 [확인근거]를 보조로 쓴다. 그래도 못 찾으면
    빈 리스트를 반환한다 — 호출부(L3)가 이 경우 캡션 자체를 렌더링하지 않는다.
    같은 문서명이 텍스트에 여러 번 나오면 처음 나온 페이지(구간)만 대표로 남긴다.
    """
    text = evidence_page_text(note_scoring_model_25)
    if not text:
        text = parse_scoring_note(note_manual_ai_scoring_26).get("confirmedBasis")
    if not text:
        return []

    seen: dict[str, str] = {}
    order: list[str] = []
    for doc, page in _DOC_PAGE_REVERSED_RE.findall(text):
        if doc not in seen:
            seen[doc] = f"{doc} {page}"
            order.append(doc)
    for doc, page in _DOC_PAGE_DOTTED_RE.findall(text):
        if doc not in seen:
            seen[doc] = f"{doc} p.{page}"
            order.append(doc)
    return [seen[d] for d in order]


# ── 판단근거 / 확인근거 / 감점사유 / 보완증빙 (best-effort) ──────────
_SECTION_RE = re.compile(r"\[(판단근거|확인근거|감점사유|보완\s*필요\s*증빙)\]")

_SECTION_KEY_MAP = {
    "판단근거": "judgmentBasis",
    "확인근거": "confirmedBasis",
    "감점사유": "deductionReason",
    "보완필요증빙": "requiredEvidenceNote",
}


class StructuredNote(TypedDict, total=False):
    summaryLine: str
    judgmentBasis: str
    confirmedBasis: str
    deductionReason: str
    requiredEvidenceNote: str
    raw: str
    structured: bool


def parse_scoring_note(note_manual_ai_scoring_26: Optional[str]) -> StructuredNote:
    """비고 - 손채점 + AI채점 - 26년 컬럼을 구조화한다.

    DN오토모티브 계열은 대체로 `[판단근거] ... [확인근거] ... [감점사유] ... [보완 필요 증빙] ...`
    브래킷 마커를 쓰고, 하나마이크론 계열은 자유 서술이라 마커가 거의 없다.
    마커를 하나도 못 찾으면 raw 원문만 채우고 structured=False로 표시한다.
    """
    text = (note_manual_ai_scoring_26 or "").strip()
    if not text:
        return {"raw": "", "structured": False}

    first_line = text.split("\n", 1)[0].strip()
    summary_line = first_line[:120] if first_line and not first_line.startswith("[") else ""

    matches = list(_SECTION_RE.finditer(text))
    if not matches:
        result: StructuredNote = {"raw": text, "structured": False}
        if summary_line:
            result["summaryLine"] = summary_line
        return result

    result = {"raw": text, "structured": True}
    if summary_line:
        result["summaryLine"] = summary_line

    for i, m in enumerate(matches):
        label = re.sub(r"\s+", "", m.group(1))
        key = _SECTION_KEY_MAP.get(label)
        if not key:
            continue
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        value = text[start:end].strip(" \n|")
        if value:
            result[key] = value  # type: ignore[literal-required]

    return result


# ── 해결방안 3분할 (현재 문제점 / 개선방향 / 필요 근거) ─────────────
# DN오토모티브: "[현재 문제점] ... [개선방향] ... [필요 근거] ..."
# 하나마이크론: "[26년 현황] ... [개선방향] ... [필요 근거] ..." (첫 마커 표현만 다름)
_SOLUTION_RE = re.compile(r"\[(현재\s*문제점|26년\s*현황|개선방향|필요\s*근거)\]")
_SOLUTION_KEY_MAP = {
    "현재문제점": "problem",
    "26년현황": "problem",
    "개선방향": "direction",
    "필요근거": "evidence",
}


class SolutionSplit(TypedDict, total=False):
    problem: str
    direction: str
    evidence: str
    raw: str
    structured: bool


def parse_solution(solution_text: Optional[str]) -> SolutionSplit:
    text = (solution_text or "").strip()
    if not text:
        return {"raw": "", "structured": False}

    matches = list(_SOLUTION_RE.finditer(text))
    if not matches:
        return {"raw": text, "structured": False}

    result: SolutionSplit = {"raw": text, "structured": True}
    for i, m in enumerate(matches):
        label = re.sub(r"\s+", "", m.group(1))
        key = _SOLUTION_KEY_MAP.get(label)
        if not key:
            continue
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        value = text[start:end].strip(" \n|")
        if value:
            result[key] = value  # type: ignore[literal-required]
    return result
