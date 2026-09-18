"""사내 문서 유사도 검색 + AI 상담 답변 생성.

`data/rag_index.sqlite3`(scripts/build_rag_index.py로 생성)에 저장된, 회사별 문서 청크
임베딩(Gemini gemini-embedding-001, 768차원)을 메모리에 올려 코사인 유사도로 top-k를 뽑고,
Gemini generateContent로 답변을 만든다.

인용은 모델이 지어내지 않도록, 실제로 검색된 청크만 citations로 내려준다
(사양서 F5-03 "인용 강제 답변 — 근거 없으면 단정 금지"에 대응).
"""
import html
import json
import sqlite3
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import numpy as np

from .config import get_settings
from .gemini_client import embed_query, generate_grounded, generate_json

_lock = threading.Lock()

# esg_diagnosis(Supabase)의 회사명과 정확히 맞추기 위해 코드 기준으로 정규화한다.
# (원본 chroma 메타데이터의 company_name 표기가 일부 행에서 미세하게 달라 이름 기준으로 묶으면
#  일부 청크가 누락된다.)
CODE_TO_COMPANY = {
    "007340": "DN오토모티브",
    "067310": "하나마이크론",
}


class CompanyIndex:
    def __init__(self, rows: list[dict], matrix: np.ndarray):
        self.rows = rows
        # 코사인 유사도를 내적으로 계산할 수 있도록 미리 정규화
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self.matrix = matrix / norms

    def search(self, query_vec: list[float], top_k: int = 5) -> list[dict]:
        if not self.rows:
            return []
        q = np.asarray(query_vec, dtype=np.float32)
        qn = np.linalg.norm(q)
        if qn == 0:
            return []
        q = q / qn
        scores = self.matrix @ q
        top_idx = np.argsort(-scores)[:top_k]
        results = []
        for idx in top_idx:
            row = dict(self.rows[int(idx)])
            row["score"] = float(scores[idx])
            results.append(row)
        return results

    def search_many(self, query_vecs: list[list[float]], top_k: int = 8) -> list[dict]:
        """여러 쿼리 벡터로 각각 검색한 뒤 id 기준으로 합치고(최고 점수 유지) 점수순 top_k를 반환한다.

        서로 다른 표현(원 질문 / 항목 용어로 보강한 질문)으로 검색하면 한 번의 검색보다
        재현율(recall)이 좋아진다 — 흔한 쿼리 확장(query expansion) 기법.
        """
        best: dict[int, dict] = {}
        for qv in query_vecs:
            for row in self.search(qv, top_k=top_k):
                rid = row["id"]
                if rid not in best or row["score"] > best[rid]["score"]:
                    best[rid] = row
        return sorted(best.values(), key=lambda r: -r["score"])[:top_k]


@lru_cache
def _load_index() -> dict[str, CompanyIndex]:
    settings = get_settings()
    db_path = Path(settings.rag_db_path)
    if not db_path.is_absolute():
        db_path = Path(__file__).resolve().parent.parent / settings.rag_db_path
    if not db_path.exists():
        return {}

    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    cur = con.execute(
        "SELECT id, company_code, company_name, doc_id, doc_type, year, page, "
        "section_title, content_type, text, table_data, embedding FROM chunks"
    )
    by_company: dict[str, list[dict]] = {}
    vectors: dict[str, list[np.ndarray]] = {}
    for r in cur:
        company = CODE_TO_COMPANY.get(r["company_code"]) or r["company_name"] or r["company_code"] or "unknown"
        vec = np.frombuffer(r["embedding"], dtype=np.float32)
        by_company.setdefault(company, []).append(
            {
                "id": r["id"],
                "doc_id": r["doc_id"],
                "doc_type": r["doc_type"],
                "year": r["year"],
                "page": r["page"],
                "section_title": r["section_title"],
                "content_type": r["content_type"],
                "text": r["text"],
                "table_data": r["table_data"],
            }
        )
        vectors.setdefault(company, []).append(vec)
    con.close()

    indexes: dict[str, CompanyIndex] = {}
    for company, rows in by_company.items():
        matrix = np.vstack(vectors[company]) if vectors[company] else np.zeros((0, 768), dtype=np.float32)
        indexes[company] = CompanyIndex(rows, matrix)
    return indexes


def index_status() -> dict[str, int]:
    """회사별 색인된 청크 수. 관리/디버깅용."""
    return {company: len(idx.rows) for company, idx in _load_index().items()}


DOC_TYPE_LABEL = {
    "business_report": "사업보고서",
    "sustainability_report": "지속가능경영보고서",
    "governance_report": "기업지배구조보고서",
}


def _format_doc_name(row: dict) -> str:
    label = DOC_TYPE_LABEL.get(row.get("doc_type"), row.get("doc_type") or "문서")
    year = row.get("year")
    return f"{label}{f' ({year}년)' if year else ''}"


def _cell(v: Any) -> str:
    if v is None:
        return ""
    return html.escape(str(v)).replace("\n", "<br/>")


def _table_data_to_html(table_json: Optional[str]) -> Optional[str]:
    """원본 표 청크의 table_data(행 배열 JSON)를 근거 카드에 쓸 <table> 마크업으로 바꾼다.

    첫 행을 헤더로 취급한다 (원본이 마크다운 표로 저장될 때도 첫 행 다음에 구분선(|---|)이
    오는 방식이라 이 가정과 일치한다).
    """
    if not table_json:
        return None
    try:
        rows = json.loads(table_json)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(rows, list) or not rows:
        return None

    head, *body = rows
    thead = "<tr>" + "".join(f"<th>{_cell(c)}</th>" for c in head) + "</tr>"
    tbody = "".join("<tr>" + "".join(f"<td>{_cell(c)}</td>" for c in r) + "</tr>" for r in body)
    return f'<table class="citation-table"><thead>{thead}</thead><tbody>{tbody}</tbody></table>'


_ANSWER_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "relevantFacts": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
            "description": (
                "답을 만들기 전, [문서 발췌]·[내부 채점 근거]에서 질문과 관련된 사실만 "
                "1문장씩 뽑아 적는 작업 메모 (사고 과정). 화면에는 노출되지 않는다. "
                "관련 사실이 전혀 없으면 빈 배열."
            ),
        },
        "conclusion": {
            "type": "STRING",
            "description": "결론부터 2~3문장. 수치·기준을 인용할 땐 컨텍스트의 표현을 그대로 쓴다.",
        },
        "usedSources": {
            "type": "ARRAY",
            "items": {"type": "INTEGER"},
            "description": "conclusion의 사실 판단을 실제로 뒷받침한 [문서 발췌] 번호만 (1부터). 내부 채점 근거만 썼다면 빈 배열.",
        },
        "nextAction": {
            "type": "STRING",
            "description": "사용자가 다음에 확인·준비하면 좋을 구체적 행동 1~2문장 (증빙명, 확인 대상 등 구체적으로).",
        },
        "insufficientEvidence": {
            "type": "BOOLEAN",
            "description": "문서 발췌·내부 채점 근거 어디에도 질문에 답할 근거가 없으면 true.",
        },
    },
    "required": ["relevantFacts", "conclusion", "usedSources", "nextAction", "insufficientEvidence"],
}

_SYSTEM_PROMPT = """너는 K-ESG(한국형 ESG 진단 가이드라인) 진단 컨설팅 콘솔에 내장된 AI 상담원이다.
사용자는 자사의 ESG 진단 결과를 검토하는 컨설턴트/실무 담당자이며, 화면에 보이는 점수·근거의
배경을 더 깊이 이해하거나 다음 행동을 확인하려고 질문한다.

[컨텍스트의 두 종류]
- **내부 채점 근거**: 이 회사의 해당 진단 항목을 이미 전문 평가팀이 K-ESG 기준에 따라 채점하며
  정리해 둔 판단근거·확인근거·감점사유·해결방안이다. 이미 검증된 사내 판단이므로 그대로 신뢰하고
  활용해도 된다. 이 내용만으로 답했다면 usedSources는 비워도 된다.
- **문서 발췌 [1]..[N]**: 사업보고서·지속가능경영보고서·기업지배구조보고서에서 유사도 검색으로
  찾아낸 원문 조각이다. 질문과 실제로 관련 있는지 스스로 판단하라 — 검색되었다고 반드시
  관련 있는 것은 아니다 (예: "온실가스 배출량"과 "대기오염물질 배출농도"는 다른 지표다).

[답변 원칙]
1. relevantFacts에 먼저 컨텍스트에서 질문과 직접 관련된 사실만 뽑아 적어라. 이 단계에서 골라내지
   못한 내용은 conclusion에서도 쓰지 않는다.
2. conclusion은 relevantFacts에 적은 사실에만 근거한다. 컨텍스트에 없는 숫자·사실을 추정하거나
   지어내지 않는다. 확실하지 않으면 "~로 추정된다" 대신 insufficientEvidence=true를 선택하라.
3. 근거가 부족하면 억지로 답하지 말고 insufficientEvidence=true로 하고, conclusion에는 무엇을
   찾지 못했는지 짧게 밝힌 뒤 nextAction에 어떤 증빙·자료를 확인하면 되는지 구체적으로 안내한다.
4. usedSources는 conclusion의 각 사실 판단을 실제로 뒷받침한 문서 발췌 번호만 넣는다 (관련 없어
   보였던 번호는 넣지 않는다).
5. nextAction은 일반론이 아니라 이 회사·이 항목에 맞는 구체적 행동으로 쓴다.
6. 한국어, 컨설팅 보고서 문체(개조식이 아닌 완결된 문장, 단정적이되 담백한 어투)로 쓴다.
7. [이전 대화]가 주어지면 같은 대화의 후속 질문으로 보고 자연스럽게 이어서 답하되, 각 답의 근거는
   여전히 이번에 주어진 컨텍스트에서만 취한다."""


# ── 사내 문서로 답이 안 될 때: 웹 검색 폴백 ──────────────────────────
# insufficientEvidence=true가 나오면, 별도 호출로 Google 검색 그라운딩을 켜서 다시 묻는다.
# (구조화 출력과 검색 그라운딩 도구를 한 요청에 같이 쓰면 응답은 오지만 실제로 검색을 타지
#  않는 것을 확인했다 — 그래서 이 경로는 순수 텍스트 응답 + groundingMetadata만 쓴다.)
_WEB_SYSTEM_PROMPT = """너는 K-ESG 진단 컨설팅 콘솔의 AI 상담원이다. 사내 문서에서 답을 찾지
못한 질문에 한해 Google 검색으로 보충 조사를 한다.

규칙:
1. 검색으로 실제 찾은 사실만 말하라. 확인되지 않은 내용을 지어내거나 일반적인 통념으로 채우지 않는다.
2. 이 회사와 이 질문에 직접 관련된 결과가 없으면 "웹 검색에서도 관련 정보를 찾지 못했습니다"라고만
   짧게 답하고 끝내라. 억지로 관련 있어 보이게 포장하지 않는다.
3. 답을 찾았다면 결론부터 3~4문장 이내로 간결하게 쓰고, 문장 뒤에 어떤 출처에서 나온 내용인지
   괄호로 짧게 적어라 (예: "…B등급을 획득했다(OO뉴스, 2026.03).") — 정확한 URL은 별도로 표시되므로
   본문에는 언론사명·자료명과 날짜 정도만 적으면 된다.
4. 이 앱이 다루는 회사의 ESG(환경·사회·지배구조) 관련 질문 범위를 벗어나는 질문이면 그 취지를
   짧게 밝혀라.
5. 한국어, 컨설팅 보고서 문체로 담백하게 쓴다."""


def _web_search_query(company: str, question: str, item_context: Optional[dict[str, Any]]) -> str:
    parts = [company]
    if item_context and item_context.get("name"):
        parts.append(f"'{item_context['name']}'")
    parts.append("관련하여:")
    parts.append(question)
    return " ".join(parts)


def _web_search_fallback(
    company: str, question: str, item_context: Optional[dict[str, Any]]
) -> dict[str, Any]:
    query = _web_search_query(company, question, item_context)
    with _lock:
        grounded = generate_grounded(_WEB_SYSTEM_PROMPT, query, temperature=0.2)

    text = grounded["text"]
    sources = grounded["sources"]

    if not sources or not text:
        return {
            "conclusion": "사내 문서와 웹 검색 모두에서 이 질문에 답할 근거를 찾지 못했습니다.",
            "citations": [],
            "nextAction": "질문을 더 구체적으로 입력하거나, 관련 자료를 직접 확인해 주세요.",
            "insufficientEvidence": True,
            "viaWebSearch": True,
        }

    citations = [
        {"n": i + 1, "doc": s["title"], "url": s["uri"], "source": "web"} for i, s in enumerate(sources)
    ]
    return {
        "conclusion": text,
        "citations": citations,
        "nextAction": "웹 검색 결과이므로 사내 공식 자료·공시와 반드시 교차 확인해 주세요.",
        "insufficientEvidence": False,
        "viaWebSearch": True,
    }


def _build_search_queries(question: str, item_context: Optional[dict[str, Any]]) -> list[str]:
    """원 질문 + (있다면) 항목 용어로 보강한 질문, 두 갈래로 검색해 재현율을 높인다."""
    queries = [question]
    if item_context and item_context.get("code"):
        terms = [item_context.get("name"), item_context.get("category")]
        criteria = item_context.get("criteriaDetail")
        if criteria:
            terms.append(criteria[:300])
        data_source = item_context.get("dataSource")
        if data_source:
            terms.append(data_source[:150])
        enriched = " ".join(t for t in terms if t) + " " + question
        queries.append(enriched)
    return queries


def _item_context_block(item_context: Optional[dict[str, Any]]) -> str:
    if not item_context:
        return ""

    lines = [
        "[내부 채점 근거]",
        f"항목코드: {item_context.get('code')} ({item_context.get('name')})",
    ]
    if item_context.get("domainLabel"):
        lines.append(f"영역: {item_context['domainLabel']}")
    if item_context.get("score") is not None:
        lines.append(f"현재 점수: {item_context.get('score')} / 100  ·  근거충분성: {item_context.get('evidence') or '평가 예정'}")
    if item_context.get("urgency"):
        lines.append(f"시급성: {item_context['urgency']}")
    if item_context.get("criteriaDetail"):
        lines.append(f"K-ESG 점검기준: {item_context['criteriaDetail'][:600]}")

    note = item_context.get("scoringNote") or {}
    if note.get("structured"):
        for label, key in [("판단근거", "judgmentBasis"), ("확인근거", "confirmedBasis"), ("감점사유", "deductionReason")]:
            if note.get(key):
                lines.append(f"{label}: {note[key][:500]}")
    elif note.get("raw"):
        lines.append(f"채점 메모: {note['raw'][:500]}")

    solution = item_context.get("solutionSplit") or {}
    if solution.get("structured"):
        if solution.get("direction"):
            lines.append(f"개선방향: {solution['direction'][:400]}")
    elif solution.get("raw"):
        lines.append(f"해결방안: {solution['raw'][:400]}")

    return "\n".join(lines)


def answer_question(
    company: str,
    question: str,
    item_context: Optional[dict[str, Any]] = None,
    history: Optional[list[dict[str, str]]] = None,
    top_k: int = 8,
) -> dict[str, Any]:
    indexes = _load_index()
    idx = indexes.get(company)

    if idx is None or not idx.rows:
        return _web_search_fallback(company, question, item_context)

    search_queries = _build_search_queries(question, item_context)
    with _lock:  # httpx 클라이언트를 스레드 간 안전하게
        q_vecs = [embed_query(q) for q in search_queries]

    hits = idx.search_many(q_vecs, top_k=top_k)
    if not hits:
        return _web_search_fallback(company, question, item_context)

    context_block = "\n\n".join(
        f"[{i+1}] ({_format_doc_name(h)} · p.{h.get('page')})\n{h['text'][:1500]}" for i, h in enumerate(hits)
    )
    item_block = _item_context_block(item_context)

    history_block = ""
    if history:
        turns = "\n".join(f"Q: {h.get('question', '')}\nA: {h.get('conclusion', '')}" for h in history[-3:])
        history_block = f"\n\n[이전 대화]\n{turns}"

    user_content = (
        f"{item_block}\n\n[문서 발췌]\n{context_block}{history_block}\n\n[질문]\n{question}"
    )

    try:
        result = generate_json(_SYSTEM_PROMPT, user_content, _ANSWER_SCHEMA, temperature=0.15)
    except Exception as e:  # noqa: BLE001
        return {
            "conclusion": f"AI 응답 생성 중 오류가 발생했습니다: {e}",
            "citations": [],
            "nextAction": "잠시 후 다시 시도해 주세요.",
            "insufficientEvidence": True,
            "viaWebSearch": False,
        }

    used = set(result.get("usedSources") or [])
    citations = []
    for i, h in enumerate(hits):
        n = i + 1
        if n not in used:
            continue
        citation: dict[str, Any] = {
            "n": n,
            "doc": _format_doc_name(h),
            "page": h.get("page"),
            "snippet": (h["text"][:220] + "…") if len(h["text"]) > 220 else h["text"],
            "score": round(h.get("score", 0.0), 3),
        }
        if h.get("content_type") == "table":
            table_html = _table_data_to_html(h.get("table_data"))
            if table_html:
                citation["tableHtml"] = table_html
        citations.append(citation)
    # usedSources가 비었는데 insufficientEvidence도 false면(=내부 채점 근거만으로 답한 경우)
    # 인용은 비워 둔다 — 없는 근거를 억지로 붙이지 않는다.

    if bool(result.get("insufficientEvidence", False)):
        # 사내 문서(+내부 채점 근거)로 답이 안 되면 웹 검색으로 한 번 더 시도한다.
        # 사용자 요구사항: 근거 불충분 시 웹 검색을 시도하되, 정확한 출처가 항상 동반돼야 하고
        # 없으면 없다고 말한다 — _web_search_fallback이 그 규칙을 그대로 따른다.
        return _web_search_fallback(company, question, item_context)

    return {
        "conclusion": result.get("conclusion", ""),
        "citations": citations,
        "nextAction": result.get("nextAction", ""),
        "insufficientEvidence": False,
        "viaWebSearch": False,
    }
