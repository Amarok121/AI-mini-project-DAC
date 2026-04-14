"""공통 LangChain `ChatOpenAI` 인스턴스 (설정 연동)."""

from __future__ import annotations

from functools import lru_cache

from langchain_openai import ChatOpenAI

from app.core.config import settings


@lru_cache(maxsize=4)
def get_chat_model(*, temperature: float, json_mode: bool) -> ChatOpenAI:
    """temperature·JSON 모드 조합별로 캐시된 모델."""
    kw: dict = {
        "api_key": (settings.OPENAI_API_KEY or None),
        "model": settings.OPENAI_MODEL,
        "temperature": temperature,
    }
    if json_mode:
        kw["model_kwargs"] = {"response_format": {"type": "json_object"}}
    return ChatOpenAI(**kw)
