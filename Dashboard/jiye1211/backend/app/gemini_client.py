"""Gemini API(REST) 얇은 래퍼. 공식 SDK 대신 httpx로 직접 호출해 의존성을 최소화한다."""
from typing import Any, Optional

import httpx

from .config import get_settings

_BASE = "https://generativelanguage.googleapis.com/v1beta"
_TIMEOUT = httpx.Timeout(60.0, connect=10.0)


def _key() -> str:
    settings = get_settings()
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY가 설정되지 않았습니다 (backend/.env 확인).")
    return settings.gemini_api_key


def embed_texts(
    texts: list[str],
    task_type: str = "RETRIEVAL_DOCUMENT",
    output_dimensionality: int = 768,
    model: Optional[str] = None,
) -> list[list[float]]:
    """batchEmbedContents로 여러 텍스트를 한 번에 임베딩한다. (최대 100개/요청 권장)"""
    settings = get_settings()
    mdl = model or settings.gemini_embedding_model
    url = f"{_BASE}/{mdl}:batchEmbedContents"
    body = {
        "requests": [
            {
                "model": mdl,
                "content": {"parts": [{"text": t}]},
                "taskType": task_type,
                "outputDimensionality": output_dimensionality,
            }
            for t in texts
        ]
    }
    with httpx.Client(timeout=_TIMEOUT) as client:
        res = client.post(url, params={"key": _key()}, json=body)
        res.raise_for_status()
        data = res.json()
    return [e["values"] for e in data["embeddings"]]


def embed_query(text: str, output_dimensionality: int = 768, model: Optional[str] = None) -> list[float]:
    return embed_texts([text], task_type="RETRIEVAL_QUERY", output_dimensionality=output_dimensionality, model=model)[0]


def generate_with_functions(
    system_instruction: str,
    user_content: str,
    function_declarations: list[dict[str, Any]],
    model: Optional[str] = None,
    temperature: float = 0.1,
) -> dict[str, Any]:
    """functionDeclarations를 준 상태로 generateContent를 호출해, 모델이 고른 함수 호출을 모두 모아 반환한다.

    질문 라우팅 전용 — 구조화 출력(responseSchema)과 함수 선언은 같은 요청에 함께 쓸 수 없어
    (Gemini API 제약), 최종 답변 생성(generate_json)과는 별도의 호출로 분리한다. Gemini는 질문에
    소주제가 여러 개면 한 응답에 functionCall part를 여러 개 담아 반환할 수 있어(병렬 함수 호출),
    첫 번째만 보지 않고 전부 모은다. 실행은 하지 않는다 — 실행은 호출한 쪽이 신뢰할 수 있는
    코드에서 한다.
    """
    settings = get_settings()
    mdl = model or settings.gemini_chat_model
    url = f"{_BASE}/{mdl}:generateContent"
    body = {
        "systemInstruction": {"parts": [{"text": system_instruction}]},
        "contents": [{"role": "user", "parts": [{"text": user_content}]}],
        "tools": [{"functionDeclarations": function_declarations}],
        "toolConfig": {"functionCallingConfig": {"mode": "AUTO"}},
        "generationConfig": {"temperature": temperature},
    }
    with httpx.Client(timeout=_TIMEOUT) as client:
        res = client.post(url, params={"key": _key()}, json=body)
        res.raise_for_status()
        data = res.json()

    candidates = data.get("candidates") or []
    if not candidates:
        return {"functionCalls": [], "text": ""}

    parts = candidates[0].get("content", {}).get("parts", [])
    function_calls = [
        {"name": p["functionCall"].get("name"), "args": p["functionCall"].get("args") or {}}
        for p in parts
        if p.get("functionCall")
    ]
    if function_calls:
        return {"functionCalls": function_calls, "text": ""}

    text = "".join(p.get("text", "") for p in parts if "text" in p)
    return {"functionCalls": [], "text": text.strip()}


def generate_json(
    system_instruction: str,
    user_content: str,
    response_schema: dict[str, Any],
    model: Optional[str] = None,
    temperature: float = 0.2,
) -> dict[str, Any]:
    """구조화된 JSON 응답을 강제하는 generateContent 호출."""
    settings = get_settings()
    mdl = model or settings.gemini_chat_model
    url = f"{_BASE}/{mdl}:generateContent"
    body = {
        "systemInstruction": {"parts": [{"text": system_instruction}]},
        "contents": [{"role": "user", "parts": [{"text": user_content}]}],
        "generationConfig": {
            "temperature": temperature,
            "responseMimeType": "application/json",
            "responseSchema": response_schema,
        },
    }
    with httpx.Client(timeout=_TIMEOUT) as client:
        res = client.post(url, params={"key": _key()}, json=body)
        res.raise_for_status()
        data = res.json()

    candidates = data.get("candidates") or []
    if not candidates:
        raise RuntimeError(f"Gemini 응답에 candidates가 없습니다: {data}")
    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(p.get("text", "") for p in parts)
    import json

    return json.loads(text)
