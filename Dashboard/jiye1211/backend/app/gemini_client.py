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


def generate_grounded(
    system_instruction: str,
    user_content: str,
    model: Optional[str] = None,
    temperature: float = 0.2,
) -> dict[str, Any]:
    """Google 검색 그라운딩을 켠 generateContent 호출.

    구조화 출력(responseSchema)과 검색 그라운딩 도구를 같은 요청에 함께 쓰면 API가 에러 없이
    응답은 주지만 실제로는 검색을 타지 않는다(grounding metadata가 비어 있음) — 확인된 API 동작이라
    여기서는 순수 텍스트 응답 + groundingMetadata만 받는다. 인용은 모델이 본문에 적은 텍스트가
    아니라 이 groundingMetadata.groundingChunks(실제 검색된 출처)에서만 가져와야 한다.
    """
    settings = get_settings()
    mdl = model or settings.gemini_chat_model
    url = f"{_BASE}/{mdl}:generateContent"
    body = {
        "systemInstruction": {"parts": [{"text": system_instruction}]},
        "contents": [{"role": "user", "parts": [{"text": user_content}]}],
        "tools": [{"google_search": {}}],
        "generationConfig": {"temperature": temperature},
    }
    with httpx.Client(timeout=_TIMEOUT) as client:
        res = client.post(url, params={"key": _key()}, json=body)
        res.raise_for_status()
        data = res.json()

    candidates = data.get("candidates") or []
    if not candidates:
        return {"text": "", "sources": [], "queries": []}

    cand = candidates[0]
    parts = cand.get("content", {}).get("parts", [])
    text = "".join(p.get("text", "") for p in parts if "text" in p)

    grounding = cand.get("groundingMetadata") or {}
    sources = []
    seen_uris: set[str] = set()
    for chunk in grounding.get("groundingChunks", []):
        web = chunk.get("web") or {}
        uri = web.get("uri")
        if not uri or uri in seen_uris:
            continue
        seen_uris.add(uri)
        sources.append({"title": web.get("title") or uri, "uri": uri})

    return {
        "text": text.strip(),
        "sources": sources,
        "queries": grounding.get("webSearchQueries", []),
    }


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
