"""
LLM-based search query/keyword generation for Scientific retrieval.

We generate:
- `query`: a single search string (<= 500 chars) for OpenAlex/arXiv/S2.
- `kws`: a short keyword list for relevance filtering and grading.

If OPENAI_API_KEY is missing or LLM fails, we fall back to heuristic helpers.
"""

from __future__ import annotations

import logging
from typing import Any, Tuple

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate

from app.core.config import settings
from app.schemas.claim import Claim

from app.agents.langchain_setup import get_chat_model

logger = logging.getLogger(__name__)


_SCHEMA_HINT = """{
  "query": string,
  "keywords": string[]
}"""

_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (
                "You craft a single academic search query and a short keyword list for scientific paper retrieval.\n"
                "Context: carbon capture / Direct Air Capture (DAC). Avoid unrelated 'DAC' acronyms.\n"
                "Rules:\n"
                "- Use claim text to bias the query toward the measurement type (e.g., continuous operation hours, durability, pilot).\n"
                "- Keep `query` <= 500 characters.\n"
                "- Return 8-20 `keywords` (mix of English/Korean OK) used for relevance filtering.\n"
                "- Include terms like: direct air capture, DAC, CO2 capture, sorbent, adsorption when relevant.\n"
                "- If claim mentions hours/continuous operation, include: continuous operation, hours, durability, stability, long-term.\n"
                "Return JSON only. Schema:\n"
                f"{_SCHEMA_HINT}\n"
            ),
        ),
        ("user", "{claims_block}"),
    ]
)


def _chain():
    return _PROMPT | get_chat_model(temperature=0.2, json_mode=True) | JsonOutputParser()


def _claims_block(claims: list[Claim]) -> str:
    lines: list[str] = []
    for c in claims[:8]:
        lines.append(f"- 기술: {c.technology} | 타입: {c.type} | 주장: {c.claim} | 적용: {c.application} | 상태: {c.status}")
    return "\n".join(lines) if lines else "- (클레임 없음)"


def _dedupe_kws(kws: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for k in kws:
        s = (k or "").strip()
        if not s:
            continue
        low = s.lower()
        if low in seen:
            continue
        seen.add(low)
        out.append(s)
    return out


async def build_scientific_query_and_keywords_llm(
    claims: list[Claim],
    *,
    fallback_query: str,
    fallback_kws: list[str],
) -> Tuple[str, list[str]]:
    if not (settings.OPENAI_API_KEY or "").strip():
        return fallback_query, fallback_kws

    try:
        data: Any = await _chain().ainvoke({"claims_block": _claims_block(claims)})
    except Exception as exc:  # noqa: BLE001
        logger.warning("scientific query LLM failed: %s", exc)
        return fallback_query, fallback_kws

    if not isinstance(data, dict):
        return fallback_query, fallback_kws

    q = str(data.get("query") or "").strip()
    kws_raw = data.get("keywords")
    kws: list[str] = []
    if isinstance(kws_raw, list):
        kws = [str(x).strip() for x in kws_raw if str(x).strip()]

    q = q[:500] if q else fallback_query
    kws = _dedupe_kws(kws)[:24] if kws else fallback_kws
    return q, kws

