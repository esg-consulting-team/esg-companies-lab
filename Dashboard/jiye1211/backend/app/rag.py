"""사내 문서 유사도 검색 + Supabase 정형 데이터 조회 + AI 상담 답변 생성.

질문이 오면 먼저 Gemini function calling으로 라우팅한다(_route_calls) — 종합점수·로드맵·
벤치마킹 대상처럼 정형 데이터 조회가 필요한 소주제는 supabase_lookup의 함수를 호출하고,
문서 내용이 필요한 소주제는 search_documents를 호출한다. 질문에 소주제가 여러 개면 함수를
여러 개 병렬로 호출할 수 있고, 벤치마킹·비교·사례류 질문은 정형 데이터를 찾았어도 항상
search_documents를 함께 호출하도록 강제한다(_needs_doc_search_anyway). 이렇게 모인 모든
결과를 _answer가 한 번에 종합해 답한다 — 정형 데이터가 질문의 일부만 답했다고 문서 검색을
건너뛰지 않고, 두 출처를 함께 본 뒤에도 못 찾은 부분만 근거 부족으로 남긴다.

문서 검색 경로는 `data/rag_index.sqlite3`(scripts/build_rag_index.py로 생성)에 저장된, 회사별
문서 청크 임베딩(Gemini gemini-embedding-001, 768차원)을 메모리에 올려 코사인 유사도로 top-k를
뽑는다.

인용은 모델이 지어내지 않도록, 실제로 검색된 청크만 citations로 내려준다
(사양서 F5-03 "인용 강제 답변 — 근거 없으면 단정 금지"에 대응). 근거를 못 찾으면 웹검색으로
보완하지 않고, 어떤 증빙이 필요한지 안내하는 것으로 마무리한다.
"""
import json
import re
import sqlite3
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import numpy as np

from . import supabase_lookup
from .config import get_settings
from .gemini_client import embed_query, generate_json, generate_with_functions
from .repository import fetch_company_code

_lock = threading.Lock()

# esg_diagnosis(Supabase)의 회사명과 정확히 맞추기 위해 코드 기준으로 정규화한다.
# (원본 chroma 메타데이터의 company_name 표기가 일부 행에서 미세하게 달라 이름 기준으로 묶으면
#  일부 청크가 누락된다.) 벤치마킹 대상 회사는 scripts/build_rag_index.py가 실제로 임베딩해
#  rag_index.sqlite3에 넣어야 검색이 되며, 여기 매핑은 그 이후를 대비해 미리 맞춰 둔 것이다.
CODE_TO_COMPANY = {
    "007340": "DN오토모티브",
    "067310": "하나마이크론",
    "267260": "HD현대일렉트릭",
    "010120": "엘에스일렉트릭",
    "361610": "SK아이이테크놀로지",
    "001440": "대한전선",
    "009150": "삼성전기",
    "000660": "SK하이닉스",
    "005930": "삼성전자",
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
        "section_title, content_type, text, embedding FROM chunks"
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


def _format_doc_name(row: dict, include_company: bool = False) -> str:
    label = DOC_TYPE_LABEL.get(row.get("doc_type"), row.get("doc_type") or "문서")
    year = row.get("year")
    name = f"{label}{f' ({year}년)' if year else ''}"
    if include_company and row.get("company"):
        return f"{row['company']} {name}"
    return name


# ── 근거 카드용 스니펫 정리: 깨진 표 잔해 감지 + 요약 ──────────────────────
# PDF에서 추출한 표 청크는 원래 행·열 구조가 깨져서 "|---|---|" 구분선이나 "| | | |"처럼
# 빈 셀만 나열된 줄로 들어오는 경우가 많다. 이런 줄을 그대로 근거 카드에 보여주면 사용자가
# 읽을 수 없는 깨진 표로 보이므로, 의미 있는 문장·숫자가 있는 줄만 추려 1~2줄 스니펫으로
# 만들고, 그마저도 없으면 스니펫 없이 "(표 데이터)"만 표시한다(출처는 이미 카드 상단에
# 문서명·페이지로 표시됨).
_MD_TABLE_LINE_RE = re.compile(r"^[|\s:-]+$")


def _has_broken_table_markup(text: str) -> bool:
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if _MD_TABLE_LINE_RE.match(s):
            return True
        if s.count("|") >= 3:
            cells = [c.strip() for c in s.split("|")]
            non_empty = [c for c in cells if c]
            if len(non_empty) <= max(1, len(cells) // 3):
                return True
    return False


def _extract_meaningful_snippet(text: str, max_lines: int = 2, max_chars: int = 220) -> Optional[str]:
    meaningful: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s or _MD_TABLE_LINE_RE.match(s):
            continue
        cleaned = re.sub(r"\s*\|\s*", " ", s).strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        if len(re.sub(r"[^0-9A-Za-z가-힣]", "", cleaned)) < 4:
            continue  # 기호·공백뿐이거나 한두 글자짜리 표 라벨 잔해
        meaningful.append(cleaned)
        if len(meaningful) >= max_lines:
            break
    if not meaningful:
        return None
    snippet = " / ".join(meaningful)
    return (snippet[:max_chars] + "…") if len(snippet) > max_chars else snippet


def _build_citation_snippet(row: dict) -> str:
    text = row["text"]
    if row.get("content_type") == "table" or _has_broken_table_markup(text):
        return _extract_meaningful_snippet(text) or "(표 데이터)"
    return (text[:220] + "…") if len(text) > 220 else text


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

[컨텍스트의 세 종류]
- **내부 채점 근거**: 이 회사의 해당 진단 항목을 이미 전문 평가팀이 K-ESG 기준에 따라 채점하며
  정리해 둔 판단근거·확인근거·감점사유·해결방안이다. 이미 검증된 사내 판단이므로 그대로 신뢰하고
  활용해도 된다.
- **정형 데이터 조회 결과**: 질문에 답하기 위해 방금 Supabase/보고서 원본에서 실제로 조회한 값
  (종합점수·등급, 항목별 서술형 평가, 시급성 분포, 로드맵 과제, 벤치마킹 대상 회사명 등)이다.
  모델이 지어낸 것이 아니므로 그대로 신뢰해도 된다. found가 false인 조회 결과는 "그 부분은
  못 찾았다"는 뜻이지 전체가 근거 부족이라는 뜻이 아니다. scope가 "full"이고 items 배열이
  있으면 그건 사용자가 전체 목록을 요청했다는 뜻이다 — 몇 개만 요약해서 보여주거나 "나머지는
  시스템에서 지원하지 않는다"는 식으로 둘러대지 말고, items 배열에 있는 항목을 전부(개수만큼
  전부) conclusion에 나열하라. 반드시 실제 줄바꿈 문자(\n)로 한 줄에 하나씩 적어라 — 쉼표나
  가운뎃점으로 한 문단에 이어 붙이지 마라. 첫 줄에 "총 N개 목록:" 같은 제목을 한 줄 쓰고,
  그다음부터 각 줄을 "코드 — 이름" 형식(예: "P-1-1 — ESG 정보공시 방식")으로 한 항목씩 적는다.
  화면이 스크롤되므로 개수가 많아도 다 보여줘도 된다. scope가 "summary"거나 아예 없으면 지금처럼
  개수와 대표 몇 개만 자연스러운 문장으로 요약한다.
- **문서 발췌 [1]..[N]**: 사업보고서·지속가능경영보고서·기업지배구조보고서에서 유사도 검색으로
  찾아낸 원문 조각이다. 질문과 실제로 관련 있는지 스스로 판단하라 — 검색되었다고 반드시
  관련 있는 것은 아니다 (예: "온실가스 배출량"과 "대기오염물질 배출농도"는 다른 지표다).
  이 내용만으로 답했다면 usedSources에 뒷받침한 번호를 넣고, 내부 채점 근거·정형 데이터
  조회 결과만으로 답한 부분은 usedSources에 넣지 않는다.

[여러 출처 종합 원칙]
- 질문에 소주제가 여러 개(예: "A 목표는? B 지표는? C는 어떻게 돼?")면, 위 세 종류의 컨텍스트 중
  각 소주제와 관련된 것을 각각 찾아 모두 활용하라. 한 소주제에 쓸 근거를 찾았다고 다른 소주제를
  건너뛰지 마라.
- 정형 데이터 조회 결과가 질문의 일부에 답했더라도, 문서 발췌가 함께 주어졌다면(벤치마킹·비교·
  사례·타사 동향처럼 서사적 맥락이 필요한 질문에서 특히) 문서 발췌도 반드시 검토해서 정형
  데이터를 뒷받침하거나 보완하는 내용이 있으면 conclusion에 함께 반영하라.
- conclusion에서 출처를 구분해서 써라 — 정형 데이터로 확인한 사실과 문서에서 확인한 사실을
  섞어 쓰지 말고 "정형 데이터 기준으로는 ~", "문서 확인 결과 ~"처럼 구분되게 서술한다.
- 문서 발췌 라벨에 회사명이 붙어 있으면(예: "[3] (삼성전기 지속가능경영보고서 (2024년) · p.12)")
  벤치마킹 대상 회사 문서까지 함께 검색된 것이다. 이 경우 conclusion에서 회사별로 구분해서
  서술하라 (예: "삼성전기는 ~, SK하이닉스는 ~이다. 반면 귀사는 ~"). 서로 다른 회사의 수치를
  하나로 뭉뚱그려 말하지 마라. 라벨에 회사명이 없는 발췌는 모두 질문 대상 회사(귀사) 문서다.

[표 형태 발췌 처리 원칙]
문서 발췌 중 일부는 PDF에서 표를 추출한 것이라 원래의 행·열 구조가 깨져서 텍스트로 들어온다.
아래 신호 중 하나라도 보이면 그 발췌를 "표 형태"로 간주하라 — 발췌 앞에 "(표 형태 발췌)"라고
표시돼 있거나, 표시가 없어도 ①한두 단어짜리 짧은 조각이 여러 줄에 걸쳐 나열되어 있거나(정상
문장처럼 이어지지 않음) ②"|"로 구분된 markdown 표 잔해나 "|---|" 구분선이 보이거나 ③연도·
페이지 번호("2021년 2022년 2023년", "24", "25" 등)만 나열된 헤더 잔해가 보이는 경우다.

표 형태로 판단되면:
1. 표 안에서 질문에 필요한 핵심 수치·항목 한두 개만 정확히 식별할 수 있으면, 그 수치만 뽑아
   자연스러운 문장으로 conclusion에 반영하라 (예: "용수 재활용률은 2025년 34%, 2030년 50%를
   목표로 한다"). 깨진 셀 구조나 빈 칸을 그대로 옮겨 적지 마라.
2. 질문에 답하려면 표 전체 구조(여러 컬럼·병합셀 등 다수의 항목을 동시에 비교해야 하는 경우)가
   필요한데 깨진 텍스트만으로는 정확히 복원할 수 없다면, 무리하게 표를 재구성하거나 빈 칸을
   추측해 채우지 말고 conclusion에 "자세한 표는 [문서명] p.[페이지] 참고"라고만 안내하라.
3. 표가 아닌 일반 산문 발췌는 이 원칙과 무관하게 지금처럼 자연스러운 문장으로 종합한다.

[답변 원칙]
1. relevantFacts에 먼저 컨텍스트에서 질문과 직접 관련된 사실만 뽑아 적어라. 이 단계에서 골라내지
   못한 내용은 conclusion에서도 쓰지 않는다.
2. conclusion은 relevantFacts에 적은 사실에만 근거한다. 컨텍스트에 없는 숫자·사실을 추정하거나
   지어내지 않는다. 확실하지 않으면 "~로 추정된다" 대신 insufficientEvidence=true를 선택하라.
3. insufficientEvidence=true는 질문 전체에 대해 내부 채점 근거·정형 데이터 조회 결과·문서
   발췌 어디에도 쓸 근거가 하나도 없을 때만 선택한다. 질문의 일부만 근거가 없다면
   insufficientEvidence는 false로 두고, 답할 수 있는 부분은 답한 뒤 conclusion 안에 "다만 ~는
   확인되지 않는다" 식으로 어느 부분이 근거 부족인지 명시하라. 문서 발췌가 주어지지 않았다면
   아직 문서 검색을 해보지 않았다는 뜻이니, 그 경우가 아닌 한 문서를 확인해 보지 않고
   insufficientEvidence=true로 단정하지 마라.
4. usedSources는 conclusion의 각 사실 판단을 실제로 뒷받침한 문서 발췌 번호만 넣는다 (관련 없어
   보였던 번호는 넣지 않는다).
5. nextAction은 일반론이 아니라 이 회사·이 항목에 맞는 구체적 행동으로 쓴다. 근거 부족인 부분이
   있으면 어떤 자료를 확인하면 되는지 그 부분에 한해 구체적으로 안내한다.
6. 한국어, 컨설팅 보고서 문체(개조식이 아닌 완결된 문장, 단정적이되 담백한 어투)로 쓴다.
7. [이전 대화]가 주어지면 같은 대화의 후속 질문으로 보고 자연스럽게 이어서 답하되, 각 답의 근거는
   여전히 이번에 주어진 컨텍스트에서만 취한다."""


# ── 사내 문서로 답이 안 될 때: 웹검색 없이 "필요한 증빙 안내"로만 마무리 ──────────
# 요구사항: 근거를 못 찾으면 웹검색으로 보완하지 않는다. 회사 문서 색인이 아예 없거나
# (idx is None), 검색된 청크가 하나도 없을 때(hits가 빔) 쓰는 정적 안내문.
def _no_evidence_response(reason: str) -> dict[str, Any]:
    return {
        "conclusion": reason,
        "citations": [],
        "nextAction": "질문과 관련된 사업보고서·지속가능경영보고서·기업지배구조보고서 등 필요한 증빙 자료를 확인해 주세요.",
        "insufficientEvidence": True,
    }


# ── Supabase 정형 데이터 조회 + 문서 검색 (병렬 function calling) ──────────
# "종합점수 몇 점이야?", "이 항목 로드맵에 포함돼?" 같이 문서 유사도 검색이 아니라
# esg_diagnosis/company_esg_yearly/esg_item_narrative/esg_roadmap_* 같은 정형 데이터를 봐야
# 답할 수 있는 질문은, Gemini가 함수 선언을 보고 스스로 어떤 함수를 호출할지 판단하게 한다.
# 질문이 여러 소주제로 이뤄져 있거나(예: 온실가스+용수+반도체특화) 벤치마킹·비교·사례처럼
# 정형 데이터만으로는 부족한 유형이면 여러 함수(같은 함수를 인자만 바꿔 여러 번 포함)를
# 한 번에 병렬로 호출하도록 유도한다 — 라우팅에서 함수를 하나만 고르고 끝내지 않는다.
_ROUTER_SYSTEM_PROMPT = """너는 K-ESG 진단 콘솔의 질문 라우터다. 사용자 질문에 답하는 데 필요한
함수를 모두 골라 호출하라(여러 개를 동시에 호출해도 된다). 답변 자체는 만들지 않는다.

- get_company_summary: 회사의 ESG 종합점수·등급(종합/E/S/G) 자체, 또는 반도체 업종 보정
  (반도체제외) 점수를 묻는 질문.
- get_item_detail: 특정 진단 항목의 채점 근거·서술형 평가(충족수준·개선방향·후속조치·벤치마크
  사례)를 묻는 질문. 질문에 항목코드가 명시돼 있으면 itemCode에 넣고, 명시돼 있지 않지만
  [내부 채점 근거]로 현재 화면의 항목이 주어져 있다면 itemCode를 비운 채 호출해도 된다.
- get_items_by_urgency: 시급성(즉시/중기/장기)별 과제 개수·목록을 묻는 질문.
- get_roadmap_urgency_distribution: 로드맵 특정 단계(번호)의 시급성 분포·과제 구성을 묻는 질문.
- get_report_insight: 컨설팅 보고서 고유 데이터(유사 선례, KCGS 등급 상관도, 3개년 연속 0점
  항목, 진단의 일반적 한계, 다음 진단 안내, 벤치마크 누락 영역, 그룹 점수 추이, 판정 확인 중
  항목 등)를 묻는 질문.
- get_benchmark_peer_names: 이 회사의 벤치마킹 대상 회사가 어디인지(실명 목록)를 묻는 질문.
- search_documents: 사업보고서·지속가능경영보고서·기업지배구조보고서 원문 유사도 검색. 위
  경우에 해당하지 않는 질문의 기본값이며, query에 이 검색에 맞게 다듬은 질의를 넣어라(생략하면
  원 질문 그대로 검색한다).

[여러 함수를 함께 호출해야 하는 경우 — 절대 하나만 고르고 끝내지 마라]
1. 질문에 서로 다른 소주제가 여러 개 있으면(예: "온실가스 배출 목표는? 용수 재활용률은?
   반도체 특화 지표는 뭐가 있어?") 소주제 개수만큼 함수를 각각 호출하라. 같은 함수라도
   항목코드·주제(topic)·검색 질의(query)를 다르게 해서 여러 번 호출할 수 있다. 소주제 중
   일부가 애매하면 그 소주제에 한해 search_documents를 추가로 호출하라.
2. 질문에 "벤치마킹", "벤치마킹사", "다른 기업", "타사", "동종업계", "비교", "사례", "선례",
   "어떻게 하고 있"같은 표현이 있으면, 정형 데이터 함수(get_benchmark_peer_names 등)를
   호출하더라도 항상 search_documents도 함께 호출하라 — 정형 데이터에는 숫자·이름만 있고
   실제 비교 맥락·서술은 문서에만 있는 경우가 많다.

[이전 대화가 주어졌을 때 — 지시어를 반드시 이전 답변으로 풀어서 해석하라]
질문에 "그거", "그 항목들", "그 26개", "방금 그거", "위에서 말한" 같은 지시어가 있으면 이번
질문만 보지 말고 [이전 대화]의 직전 답변이 무엇에 대한 것이었는지부터 확인하라. 예를 들어
직전 답변이 "즉시 개선 필요 항목은 총 26개입니다"였고 이번 질문이 "그 26개 항목이 뭔지
알려줘"라면, 이는 get_items_by_urgency를 그 즉시/중기/장기 등급 그대로 다시 호출하되
scope="full"로 호출하라는 뜻이다 — 이런 지시어가 있는데도 이전 대화와 무관하게 함수를 고르지
못하거나 아예 호출하지 않고 넘어가지 마라."""

_FUNCTION_DECLARATIONS = [
    {
        "name": "get_company_summary",
        "description": "이 회사의 최신 연도 ESG 종합점수·등급(종합/E/S/G)과 반도체제외 보정 점수를 조회한다.",
        "parameters": {"type": "OBJECT", "properties": {}},
    },
    {
        "name": "get_item_detail",
        "description": "특정 진단 항목의 채점 데이터(esg_diagnosis)와 서술형 평가(esg_item_narrative)를 함께 조회한다.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "itemCode": {
                    "type": "STRING",
                    "description": "질문에 명시된 항목코드(예: G-1-3). 명시돼 있지 않으면 생략 — 현재 화면의 항목으로 처리된다.",
                },
            },
        },
    },
    {
        "name": "get_items_by_urgency",
        "description": "시급성(즉시/중기/장기)별 진단 항목 개수 또는 전체 목록을 조회한다.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "urgencyLevel": {
                    "type": "STRING",
                    "enum": ["즉시", "중기", "장기"],
                    "description": "질문이 묻는 시급성 등급.",
                },
                "scope": {
                    "type": "STRING",
                    "enum": ["summary", "full"],
                    "description": (
                        "'summary'(기본값): '몇 개야', '개수' 같은 단순 질문 — 개수와 대표 몇 개만 "
                        "필요. 'full': '다 뭐야', '목록', '전부 알려줘', 이전 답변에서 언급된 개수를 "
                        "가리키며 '그거 다 뭐야' 같은 전체 요청 — 전체 항목코드·이름 목록이 필요."
                    ),
                },
            },
            "required": ["urgencyLevel"],
        },
    },
    {
        "name": "get_roadmap_urgency_distribution",
        "description": "로드맵 특정 단계에 포함된 과제들의 관련 항목을 시급성별(즉시/중기/장기)로 집계한다.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "stageNo": {"type": "INTEGER", "description": "질문이 묻는 로드맵 단계 번호(1부터)."},
            },
            "required": ["stageNo"],
        },
    },
    {
        "name": "get_report_insight",
        "description": (
            "컨설팅 보고서(docx) 원문에서 추출한 정형 데이터를 topic으로 조회한다. topic은 다음 중 "
            "하나: precedentCases(유사 선례), kcgsCorrelation(KCGS 등급 상관도), "
            "structuralZeroItems_3yearConsecutive(3개년 연속 0점 항목), generalLimitations(진단의 "
            "일반적 한계), nextDiagnosis(다음 진단 안내), benchmarkMissingDomains(벤치마크 누락 영역), "
            "groupedScoreTrend(그룹 점수 추이), pendingItems(판정 확인 중 항목), "
            "itemBreakdown(항목별 배점 구성), totalScore(총점 구성)."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "topic": {"type": "STRING", "description": "위 topic 값 중 하나."},
            },
            "required": ["topic"],
        },
    },
    {
        "name": "get_benchmark_peer_names",
        "description": "이 회사의 벤치마킹 대상 회사 실명 목록을 조회한다.",
        "parameters": {"type": "OBJECT", "properties": {}},
    },
    {
        "name": "search_documents",
        "description": "사업보고서·지속가능경영보고서·기업지배구조보고서 원문을 유사도 검색한다(위 함수들에 해당하지 않을 때의 기본값이자, 벤치마킹·비교·사례 질문에서 정형 데이터와 함께 항상 호출돼야 하는 보완 검색).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "이 소주제에 맞게 다듬은 검색 질의. 생략하면 원 질문 그대로 검색한다.",
                },
            },
        },
    },
]

_STRUCTURED_FUNCTION_NAMES = {
    "get_company_summary",
    "get_item_detail",
    "get_items_by_urgency",
    "get_roadmap_urgency_distribution",
    "get_report_insight",
    "get_benchmark_peer_names",
}

# 정형 데이터에 숫자·이름은 있어도 비교 맥락이나 서술은 없는 질문 유형 — 이 표현이 있으면
# 라우터가 문서 검색을 빠뜨렸더라도 여기서 강제로 search_documents를 추가한다(프롬프트만
# 믿지 않고 결정적으로 보장).
_FORCE_DOC_SEARCH_KEYWORDS = [
    "벤치마킹",
    "다른 기업",
    "타사",
    "동종업계",
    "비교",
    "사례",
    "선례",
    "어떻게 하고 있",
]


def _needs_doc_search_anyway(question: str) -> bool:
    return any(kw in question for kw in _FORCE_DOC_SEARCH_KEYWORDS)


def _resolve_doc_search_companies(question: str, company: str, company_code: Optional[str]) -> list[str]:
    """search_documents가 어떤 회사(들)의 색인을 볼지 정한다.

    기본은 현재 회사 하나로만 좁히는 기존 안전장치를 그대로 유지한다. 질문이 벤치마킹·비교·
    사례류 표현을 쓰거나 실제 벤치마킹 대상 회사명을 직접 언급하면, 그때만 현재 회사 +
    get_benchmark_peer_names로 조회한 벤치마킹 대상 회사들까지 검색 범위에 포함한다
    (벤치마킹 대상 보고서도 이미 색인돼 있어 검색 자체는 가능하다).
    """
    if company_code is None:
        return [company]

    peers_result = supabase_lookup.get_benchmark_peer_names(company_code)
    peers = peers_result.get("peerCompanies") or [] if peers_result.get("found") else []
    if not peers:
        return [company]

    mentions_peer_by_name = any(peer in question for peer in peers)
    if mentions_peer_by_name or _needs_doc_search_anyway(question):
        return [company] + [p for p in peers if p != company]
    return [company]


def _resolve_structured_call(
    company_code: Optional[str],
    item_context: Optional[dict[str, Any]],
    name: str,
    args: dict[str, Any],
) -> Optional[tuple[str, Any]]:
    """구조화 함수 하나를 실제로 실행해 (설명 라벨, 원본 조회 결과)를 반환한다.

    company_code가 없거나(=companies에 등록되지 않은 회사) 필요한 인자가 없으면 None을 반환해
    호출한 쪽이 그 소주제를 문서검색으로라도 커버하게 한다.
    """
    if company_code is None:
        return None

    if name == "get_company_summary":
        return ("get_company_summary", supabase_lookup.get_company_summary(company_code))
    if name == "get_item_detail":
        item_code = args.get("itemCode") or (item_context or {}).get("code")
        if not item_code:
            return None
        return (f"get_item_detail({item_code})", supabase_lookup.get_item_detail(item_code, company_code))
    if name == "get_items_by_urgency":
        urgency = args.get("urgencyLevel")
        if urgency not in ("즉시", "중기", "장기"):
            return None
        full = args.get("scope") == "full"
        return (
            f"get_items_by_urgency({urgency}, scope={'full' if full else 'summary'})",
            supabase_lookup.get_items_by_urgency(company_code, urgency, full=full),
        )
    if name == "get_roadmap_urgency_distribution":
        try:
            stage_no = int(args.get("stageNo"))
        except (TypeError, ValueError):
            return None
        return (
            f"get_roadmap_urgency_distribution(stage {stage_no})",
            supabase_lookup.get_roadmap_urgency_distribution(stage_no, company_code),
        )
    if name == "get_report_insight":
        topic = args.get("topic")
        if not topic:
            return None
        return (f"get_report_insight({topic})", supabase_lookup.get_report_insight(company_code, topic))
    if name == "get_benchmark_peer_names":
        return ("get_benchmark_peer_names", supabase_lookup.get_benchmark_peer_names(company_code))
    return None


def _route_calls(
    question: str,
    item_context: Optional[dict[str, Any]],
    history: Optional[list[dict[str, str]]] = None,
) -> list[dict[str, Any]]:
    """질문에 필요한 함수 호출 목록을 Gemini function calling으로 받는다 (0개~여러 개).

    [이전 대화]를 함께 넘겨야 "그거", "그 26개" 같은 후속 질문의 지시어가 이전 답변의
    무엇을 가리키는지 라우터가 판단할 수 있다 — 안 넘기면 이전 답변 내용을 전혀 모르는
    채로 이번 질문만 보고 함수를 골라야 해서, 안 고르거나 엉뚱한 인자로 고르게 된다.

    라우터가 아무것도 고르지 않거나(실패 포함) search_documents를 빠뜨렸는데 비교·사례류
    질문이면, 호출한 쪽(answer_question)이 search_documents를 보강한다.
    """
    note = ""
    if item_context and item_context.get("code"):
        note = f"\n\n[내부 채점 근거] 항목코드: {item_context['code']} ({item_context.get('name')})"
    history_note = ""
    if history:
        turns = "\n".join(f"Q: {h.get('question', '')}\nA: {h.get('conclusion', '')}" for h in history[-3:])
        history_note = f"\n\n[이전 대화]\n{turns}"
    try:
        with _lock:
            routed = generate_with_functions(
                _ROUTER_SYSTEM_PROMPT, question + note + history_note, _FUNCTION_DECLARATIONS
            )
    except Exception:  # noqa: BLE001
        return []
    return routed.get("functionCalls") or []


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


def _answer(
    company: str,
    company_code: Optional[str],
    question: str,
    item_context: Optional[dict[str, Any]],
    history: Optional[list[dict[str, str]]],
    top_k: int,
    calls: list[dict[str, Any]],
) -> dict[str, Any]:
    """라우터가 고른 함수 호출들을 모두 실행해 하나로 종합한다.

    구조화 함수는 각각 실행해 [정형 데이터 조회 결과: ...] 블록으로 쌓고, search_documents
    호출들은 검색어를 모아 한 번의 유사도 검색으로 합친다(idx.search_many가 여러 쿼리를 이미
    점수순으로 병합해 주므로 그대로 재사용). 마지막에 이 블록들을 한 프롬프트에 모아 단 한 번의
    generate_json으로 답을 종합한다 — 정형 데이터가 일부를 답했다고 문서 검색을 건너뛰지 않고,
    두 출처를 함께 본 뒤에도 못 찾은 부분만 insufficientEvidence로 남는다.
    """
    structured_blocks: list[str] = []
    doc_queries: list[str] = []

    for call in calls:
        name = call.get("name")
        args = call.get("args") or {}
        if name == "search_documents":
            doc_queries.append(args.get("query") or question)
        elif name in _STRUCTURED_FUNCTION_NAMES:
            resolved = _resolve_structured_call(company_code, item_context, name, args)
            if resolved is not None:
                label, data = resolved
                structured_blocks.append(f"[정형 데이터 조회 결과: {label}]\n{json.dumps(data, ensure_ascii=False)}")
            else:
                # 회사코드 미상·필수 인자 누락 등으로 실행 못 했으면, 그 소주제라도
                # 문서검색으로 커버되도록 원 질문을 검색어로 추가한다.
                doc_queries.append(question)

    hits: list[dict[str, Any]] = []
    idx_missing = False
    target_companies: list[str] = [company]
    multi_company_search = False
    if doc_queries:
        target_companies = _resolve_doc_search_companies(question, company, company_code)
        multi_company_search = len(target_companies) > 1
        all_queries = list(dict.fromkeys(doc_queries + _build_search_queries(question, item_context)))
        indexes = _load_index()
        with _lock:  # httpx 클라이언트를 스레드 간 안전하게
            q_vecs = [embed_query(q) for q in all_queries]
        # 회사를 여러 개 합쳐서 볼 때는 한쪽에 결과가 쏠리지 않도록 회사별로 상한을 나눠 갖는다
        # (자사 하나만 볼 때는 기존과 동일하게 top_k 전체를 쓴다).
        per_company_k = top_k if len(target_companies) == 1 else max(2, top_k // len(target_companies))
        any_index_found = False
        for target in target_companies:
            idx = indexes.get(target)
            if idx is None or not idx.rows:
                continue
            any_index_found = True
            for row in idx.search_many(q_vecs, top_k=per_company_k):
                row = dict(row)
                row["company"] = target
                hits.append(row)
        idx_missing = not any_index_found

    if not structured_blocks and not hits:
        if idx_missing:
            return _no_evidence_response(f"'{company}'에 대해 색인된 사내 문서가 없어 답할 근거를 찾지 못했습니다.")
        return _no_evidence_response("질문과 관련된 근거를 찾지 못했습니다.")

    item_block = _item_context_block(item_context)
    structured_block_text = "\n\n".join(structured_blocks)
    context_block = (
        "[문서 발췌]\n"
        + "\n\n".join(
            f"[{i+1}] ({_format_doc_name(h, include_company=multi_company_search)} · p.{h.get('page')}"
            f"{' · 표 형태 발췌' if h.get('content_type') == 'table' else ''})\n{h['text'][:1500]}"
            for i, h in enumerate(hits)
        )
        if hits
        else ""
    )

    history_block = ""
    if history:
        turns = "\n".join(f"Q: {h.get('question', '')}\nA: {h.get('conclusion', '')}" for h in history[-3:])
        history_block = f"[이전 대화]\n{turns}"

    user_content = "\n\n".join(
        part for part in [item_block, structured_block_text, context_block, history_block, f"[질문]\n{question}"] if part
    )

    try:
        result = generate_json(_SYSTEM_PROMPT, user_content, _ANSWER_SCHEMA, temperature=0.15)
    except Exception as e:  # noqa: BLE001
        return {
            "conclusion": f"AI 응답 생성 중 오류가 발생했습니다: {e}",
            "citations": [],
            "nextAction": "잠시 후 다시 시도해 주세요.",
            "insufficientEvidence": True,
        }

    used = set(result.get("usedSources") or [])
    citations = []
    for i, h in enumerate(hits):
        n = i + 1
        if n not in used:
            continue
        citation: dict[str, Any] = {
            "n": n,
            "doc": _format_doc_name(h, include_company=multi_company_search),
            "page": h.get("page"),
            "snippet": _build_citation_snippet(h),
            "score": round(h.get("score", 0.0), 3),
        }
        citations.append(citation)
    # usedSources가 비었는데 insufficientEvidence도 false면(=정형 데이터/내부 채점 근거만으로
    # 답한 경우) 인용은 비워 둔다 — 없는 근거를 억지로 붙이지 않는다.
    # insufficientEvidence=true여도 웹검색으로 보완하지 않는다 — 모델이 이미 conclusion/nextAction에
    # 무엇을 찾지 못했는지·어떤 증빙을 확인하면 되는지 적어 두었으므로 그대로 내려준다.

    return {
        "conclusion": result.get("conclusion", ""),
        "citations": citations,
        "nextAction": result.get("nextAction", ""),
        "insufficientEvidence": bool(result.get("insufficientEvidence", False)),
    }


def search_documents(
    company: str,
    question: str,
    item_context: Optional[dict[str, Any]] = None,
    history: Optional[list[dict[str, str]]] = None,
    top_k: int = 8,
) -> dict[str, Any]:
    """사업보고서·지속가능경영보고서·기업지배구조보고서 원문 유사도 검색 + 답변 생성.

    라우팅 없이 문서 검색 한 경로만 직접 타고 싶을 때 쓰는 진입점(예: 라우팅 자체가 완전히
    실패했을 때의 기본 동작). 내부적으로 _answer에 search_documents 호출 하나만 넘긴다.
    """
    return _answer(company, None, question, item_context, history, top_k, [{"name": "search_documents", "args": {}}])


def answer_question(
    company: str,
    question: str,
    item_context: Optional[dict[str, Any]] = None,
    history: Optional[list[dict[str, str]]] = None,
    top_k: int = 8,
) -> dict[str, Any]:
    """질문을 라우팅해 필요한 함수 호출들을 모두 실행한 뒤 하나의 답으로 종합한다.

    - 정형 데이터 함수가 선택돼도, 벤치마킹·비교·사례류 질문이면 search_documents를 항상
      함께 실행한다(정형 데이터가 답을 찾았다고 문서 검색을 건너뛰지 않는다).
    - 질문에 소주제가 여럿이면 라우터가 여러 함수를 병렬로 고를 수 있고, 그 결과를 모두 모아
      한 번에 종합 답변을 만든다.
    - 라우팅이 아무 함수도 고르지 못하면(실패 포함) search_documents 하나로 기본 동작한다.
    """
    company_code = fetch_company_code(company)
    calls = _route_calls(question, item_context, history)

    has_doc_search = any(c.get("name") == "search_documents" for c in calls)
    if not has_doc_search and (not calls or _needs_doc_search_anyway(question)):
        calls = calls + [{"name": "search_documents", "args": {}}]

    return _answer(company, company_code, question, item_context, history, top_k, calls)
