"""공통 LangChain `ChatOpenAI` 인스턴스 (설정 연동)."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.core.config import settings


def _patch_langchain_debug_compat() -> None:
    """
    `langchain_core`가 `langchain.debug` / `verbose` / `llm_cache` 등을 조회한다.
    메타 패키지에 속성이 없을 때 기본값(False)을 둔다.
    """

    try:
        import langchain  # noqa: PLC0415

        if not hasattr(langchain, "debug"):
            setattr(langchain, "debug", False)
        if not hasattr(langchain, "verbose"):
            setattr(langchain, "verbose", False)
        if not hasattr(langchain, "llm_cache"):
            setattr(langchain, "llm_cache", None)
    except Exception:  # noqa: BLE001
        pass


_patch_langchain_debug_compat()


@lru_cache(maxsize=4)
def get_chat_model(*, temperature: float, json_mode: bool) -> Any:
    """temperature·JSON 모드 조합별로 캐시된 모델."""
    from langchain_openai import ChatOpenAI

    kw: dict = {
        "api_key": (settings.OPENAI_API_KEY or None),
        "model": settings.OPENAI_MODEL,
        "temperature": temperature,
    }
    if json_mode:
        kw["model_kwargs"] = {"response_format": {"type": "json_object"}}
    return ChatOpenAI(**kw)
