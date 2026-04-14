"""공통 LangChain `ChatOpenAI` 인스턴스 (설정 연동)."""

from __future__ import annotations

from functools import lru_cache

from langchain_openai import ChatOpenAI

from app.core.config import settings


def _patch_langchain_debug_compat() -> None:
    """
    `langchain_core`가 콜백 설정 중 `langchain.debug`를 조회한다.
    일부 환경(메타 패키지/버전 조합)에서는 해당 속성이 없어 런타임 오류가 날 수 있어
    안전한 기본값(False)을 제공한다.
    """

    try:
        import langchain  # noqa: PLC0415

        if not hasattr(langchain, "debug"):
            setattr(langchain, "debug", False)
    except Exception:  # noqa: BLE001
        pass


_patch_langchain_debug_compat()


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
