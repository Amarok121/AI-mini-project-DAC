"""Step 4: 원문·스니펫을 바탕으로 보수적 규제 적용성 평가 (LangChain + OpenAI JSON)."""

from __future__ import annotations

import logging
from typing import Any, Optional

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate

from app.core.config import settings

from app.agents.langchain_setup import get_chat_model
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
  "evidence_summary": string,
  "requires_expert_review": boolean
}"""

REGULATORY_ANALYSIS_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (
                "You are a cautious regulatory analyst for industrial and climate policy. "
                "Prefer '불명확' when evidence is incomplete. Korean labels for verdict/confidence as specified."
            ),
        ),
        ("user", "{user_msg}"),
    ]
)


def _analysis_chain():
    return (
        REGULATORY_ANALYSIS_PROMPT
        | get_chat_model(temperature=0.15, json_mode=True)
        | JsonOutputParser()
    )


async def analyze_regulatory_impact(
    claims_context: str,
    portal_docs: list[PortalDocument],
    tavily_hits: list[TavilyHit],
) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    if not (settings.OPENAI_API_KEY or "").strip():
        return None, "OPENAI_API_KEY 미설정"

    portal_block = "\n\n---\n\n".join(
        f"[{d.law_name} | {d.source}]\n{d.text}" for d in portal_docs
    )
    if not portal_block.strip():
        portal_block = (
            "(정부 포털에서 가져온 텍스트가 없습니다. 아래 Tavily 스니펫만 근거로 판단하되, "
            "불확실하면 반드시 불명확 처리하세요.)"
        )

    tavily_block = "\n\n".join(
        f"[{h.title}] {h.url}\n{h.content}" for h in tavily_hits[:12]
    )

    user_msg = f"""검증할 기술·클레임 맥락:
{claims_context.strip() or "(클레임 없음)"}

--- 정부·공공 출처 텍스트 (가능한 경우) ---
{portal_block}

--- Tavily 웹 검색 스니펫 (보조 근거, 단독으로 법적 확정 불가) ---
{tavily_block}

요구사항:
- 공식 원문이 없거나 불충분하면 verdict는 "불명확", confidence는 "LOW" 또는 "MED".
- 인센티브·세제(예: 45Q)는 조건(규모, 연간 톤수 등)을 reason에 숫자와 함께 명시.
- `evidence_summary`: 교차검증·보고서용 근거 팩. 한국어 3~6문장. 어떤 출처를 근거로 했는지, 적용 가능성·불확실성·전문가 검토 필요 여부를 요약 (reason과 중복 가능하나 서술형으로 독립 읽기 가능하게).
- 환각 금지: 텍스트에 없는 조문 번호를 지어내지 마세요.
- JSON만 출력. 스키마:
{_ANALYSIS_SCHEMA_HINT}
"""

    try:
        data: Any = await _analysis_chain().ainvoke({"user_msg": user_msg})
    except Exception as exc:  # noqa: BLE001
        logger.warning("regulatory analysis chain failed: %s", exc)
        return None, str(exc)

    if not isinstance(data, dict):
        return None, "규제 해석 응답 형식 오류"

    return data, None
