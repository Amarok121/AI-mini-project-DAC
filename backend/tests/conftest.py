"""테스트 수집 전에 저장소 루트·backend의 .env를 로드해 OPENAI_API_KEY 등을 반영."""

from pathlib import Path

from dotenv import load_dotenv


def _patch_langchain_debug_compat() -> None:
    """langchain_core가 `langchain.debug`를 읽는데, 메타 패키지에 속성이 없을 때 대비."""
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

_here = Path(__file__).resolve()
_backend = _here.parents[1]
_repo = _backend.parent
load_dotenv(_repo / ".env")
load_dotenv(_backend / ".env")
