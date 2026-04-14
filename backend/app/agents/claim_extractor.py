"""클레임 추출: 정제된 본문에서 검증 가능한 기술 주장을 구조화 (LangChain + OpenAI JSON)."""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate

from app.core.config import settings
from app.schemas.claim import Claim

from app.agents.langchain_setup import get_chat_model

logger = logging.getLogger(__name__)

_MAX_INPUT_CHARS = 14_000
_MAX_CLAIMS = 10

CLAIM_EXTRACT_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (
                "You extract distinct, checkable technology claims from the user's text (Korean and/or English). "
                "Each claim should be something a reviewer could verify with literature, patents, or regulations. "
                "Return JSON only: {{\"claims\": [ ... ]}}. "
                "Each element must have: "
                "technology (short label for the tech or product), "
                "claim (the factual assertion), "
                "application (where/how it applies; empty string if unknown), "
                "type (e.g. 성능 지표, 경제성, 규제, 안전성, 일반), "
                "status: either \"달성\" (already achieved / stated as fact) or \"목표\" (goal / plan / target). "
                "If the text is vague, emit at most one broad claim. "
                "Do not invent numbers or citations not present in the text."
            ),
        ),
        ("user", "본문:\n\n{text}"),
    ]
)


def _claim_extract_chain():
    return CLAIM_EXTRACT_PROMPT | get_chat_model(temperature=0.2, json_mode=True) | JsonOutputParser()


def _normalize_status(v: Any) -> str:
    s = str(v or "").strip()
    if s in ("달성", "목표"):
        return s
    low = s.lower()
    if low in ("achieved", "done", "completed", "fact"):
        return "달성"
    if low in ("goal", "target", "planned", "plan"):
        return "목표"
    return "목표"


def _claim_from_dict(d: dict[str, Any]) -> Optional[Claim]:
    try:
        tech = str(d.get("technology") or "").strip() or "(미상)"
        cl = str(d.get("claim") or "").strip()
        if not cl:
            return None
        return Claim(
            technology=tech[:500],
            claim=cl[:2000],
            application=str(d.get("application") or "").strip()[:1000],
            type=str(d.get("type") or "일반").strip()[:200] or "일반",
            status=_normalize_status(d.get("status")),  # type: ignore[arg-type]
        )
    except Exception:  # noqa: BLE001
        return None


def _fallback_claims_from_text(text: str) -> list[Claim]:
    """API 키 없음·파싱 실패 시 최소 1건으로 파이프라인 유지."""
    t = re.sub(r"\s+", " ", (text or "").strip())
    if not t:
        return []
    snippet = t[:800] + ("…" if len(t) > 800 else "")
    return [
        Claim(
            technology="(자동 요약)",
            claim=snippet,
            application="",
            type="일반",
            status="목표",
        )
    ]


async def run_claim_extractor(text: str) -> list[Claim]:
    raw = (text or "").strip()
    if not raw:
        return []

    if not (settings.OPENAI_API_KEY or "").strip():
        logger.info("claim_extractor: OPENAI_API_KEY 없음 — 폴백 클레임 사용")
        return _fallback_claims_from_text(raw)

    truncated = raw[:_MAX_INPUT_CHARS]
    if len(raw) > _MAX_INPUT_CHARS:
        truncated += "\n\n[…본문이 길어 앞부분만 사용했습니다.]"

    try:
        data: Any = await _claim_extract_chain().ainvoke({"text": truncated})
    except Exception as exc:  # noqa: BLE001
        logger.warning("claim_extractor chain failed: %s", exc)
        return _fallback_claims_from_text(raw)

    if not isinstance(data, dict):
        return _fallback_claims_from_text(raw)

    raw_list = data.get("claims")
    if not isinstance(raw_list, list):
        return _fallback_claims_from_text(raw)

    out: list[Claim] = []
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        c = _claim_from_dict(item)
        if c:
            out.append(c)
        if len(out) >= _MAX_CLAIMS:
            break

    if not out:
        return _fallback_claims_from_text(raw)

    return out
