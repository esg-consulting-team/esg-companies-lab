"""AI 상담 챗봇 API — 대시보드(L1~L7) 라우트와 분리된 전용 라우터.

팀원이 main.py에서 L1~L7 화면 라우트를 추가·수정할 때 이 파일과 겹치지 않도록, 챗봇 관련
Pydantic 모델·엔드포인트를 모두 여기로 모았다. main.py는 이 라우터를 include_router로
붙이기만 한다(app/main.py 참고).
"""
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import rag, repository

router = APIRouter()


class ChatHistoryTurn(BaseModel):
    question: str
    conclusion: str


class ChatRequest(BaseModel):
    company: str
    question: str
    itemCode: Optional[str] = None
    history: Optional[list[ChatHistoryTurn]] = None


_ITEM_CONTEXT_FIELDS = [
    "code",
    "name",
    "category",
    "domainLabel",
    "score",
    "evidence",
    "urgency",
    "criteriaDetail",
    "dataSource",
    "scoringNote",
    "solutionSplit",
]


@router.post("/api/chat")
def chat(req: ChatRequest) -> dict:
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="질문이 비어 있습니다.")
    item_ctx = None
    if req.itemCode:
        detail = repository.build_item_detail(req.company, req.itemCode)
        if detail:
            item_ctx = {k: detail.get(k) for k in _ITEM_CONTEXT_FIELDS}
    history = [h.model_dump() for h in req.history] if req.history else None
    return rag.answer_question(req.company, req.question, item_context=item_ctx, history=history)


@router.get("/api/rag/status")
def rag_status() -> dict:
    return rag.index_status()
