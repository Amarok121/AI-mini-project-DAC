"""Step 4: 원문·스니펫을 바탕으로 보수적 규제 적용성 평가 (OpenAI JSON)."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Optional

from app.core.config import settings

from app.agents.regulatory.portal_fetch import PortalDocument
from app.agents.regulatory.tavily_search import TavilyHit

logger = logging.getLogger(__name__)


_ANALYSIS_SCHEMA_HINT = """{
  "applicable_regulations": string[],
  "incentives": string[],
  "risks": string[],
  "verdict": "해당" | "미해당" | "불명확",
  "confidence": "HIGH" | "MED" | "LOW",
  "reason": string,
  "requires_expert_review": boolean
}"""


def _openai_analyze_sync(
    claims_context: str,
    portal_docs: list[PortalDocument],
    tavily_hits: list[TavilyHit],
) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    if not (settings.OPENAI_API_KEY or "").strip():
        return None, "OPENAI_API_KEY 미설정"

    try:
        from openai import OpenAI
    except ImportError:
        return None, "openai 패키지 미설치"

    portal_block = "\n\n---\n\n".join(
        f"[{d.law_name} | {d.source}]\n{d.text}" for d in portal_docs
    )
    if not portal_block.strip():
        portal_block = "(정부 포털에서 가져온 텍스트가 없습니다. 아래 Tavily 스니펫만 근거로 판단하되, 불확실하면 반드시 불명확 처리하세요.)"

    tavily_block = "\n\n".join(
        f"[{h.title}] {h.url}\n{h.content}" for h in tavily_hits[:12]
    )

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    user_msg = f"""검증할 기술·클레임 맥락:
{claims_context.strip() or "(클레임 없음)"}

--- 정부·공공 출처 텍스트 (가능한 경우) ---
{portal_block}

--- Tavily 웹 검색 스니펫 (보조 근거, 단독으로 법적 확정 불가) ---
{tavily_block}

요구사항:
- 공식 원문이 없거나 불충분하면 verdict는 "불명확", confidence는 "LOW" 또는 "MED".
- 인센티브·세제(예: 45Q)는 조건(규모, 연간 톤수 등)을 reason에 숫자와 함께 명시.
- 환각 금지: 텍스트에 없는 조문 번호를 지어내지 마세요.
- JSON만 출력. 스키마:
{_ANALYSIS_SCHEMA_HINT}
"""

    resp = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        temperature=0.15,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a cautious regulatory analyst for industrial and climate policy. "
                    "Prefer '불명확' when evidence is incomplete. Korean labels for verdict/confidence as specified."
                ),
            },
            {"role": "user", "content": user_msg},
        ],
    )
    raw = (resp.choices[0].message.content or "").strip()
    try:
        return json.loads(raw), None
    except json.JSONDecodeError:
        logger.warning("regulatory_llm JSON failed: %s", raw[:800])
        return None, "규제 해석 JSON 파싱 실패"


async def analyze_regulatory_impact(
    claims_context: str,
    portal_docs: list[PortalDocument],
    tavily_hits: list[TavilyHit],
) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    return await asyncio.to_thread(
        _openai_analyze_sync, claims_context, portal_docs, tavily_hits
    )
