"""Step 2: Tavily 스니펫에서 법령·규정 명칭 후보 추출 (OpenAI JSON)."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Optional

from app.core.config import settings

from app.agents.regulatory.tavily_search import TavilyHit

logger = logging.getLogger(__name__)

_MAX_LAWS = 8


def _openai_extract_sync(hits: list[TavilyHit]) -> tuple[list[str], Optional[str]]:
    if not (settings.OPENAI_API_KEY or "").strip():
        return [], "OPENAI_API_KEY 미설정"

    try:
        from openai import OpenAI
    except ImportError:
        return [], "openai 패키지 미설치"

    bundle = "\n\n".join(
        f"### {i}. {h.title}\nURL: {h.url}\n{h.content}"
        for i, h in enumerate(hits, 1)
    )
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    resp = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        temperature=0.1,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "You extract concrete law, regulation, and policy names cited or implied in snippets. "
                    "Prefer official titles, article numbers, act names (e.g. IRA 45Q, 탄소중립기본법, "
                    "EU CBAM Regulation). Return JSON: {\"laws\": string[]}. "
                    "Max 8 items. If nothing reliable, {\"laws\": []}. "
                    "Do not invent names not supported by the text."
                ),
            },
            {"role": "user", "content": f"Search results:\n\n{bundle}"},
        ],
    )
    raw = (resp.choices[0].message.content or "").strip()
    try:
        data: Any = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("law_extract JSON parse failed: %s", raw[:500])
        return [], "법령명 JSON 파싱 실패"

    laws_raw = data.get("laws") if isinstance(data, dict) else None
    if not isinstance(laws_raw, list):
        return [], None

    laws: list[str] = []
    for x in laws_raw:
        if isinstance(x, str) and x.strip():
            laws.append(x.strip())
    return laws[:_MAX_LAWS], None


async def extract_law_candidates(hits: list[TavilyHit]) -> tuple[list[str], Optional[str]]:
    if not hits:
        return [], "Tavily 결과 없음"
    return await asyncio.to_thread(_openai_extract_sync, hits)
