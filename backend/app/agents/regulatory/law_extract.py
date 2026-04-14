"""Step 2: Tavily 스니펫에서 법령·규정 명칭 후보 추출 (LangChain + OpenAI JSON)."""

from __future__ import annotations

import logging
from typing import Any, Optional

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate

from app.core.config import settings

from app.agents.langchain_setup import get_chat_model
from app.agents.regulatory.tavily_search import TavilyHit

logger = logging.getLogger(__name__)

_MAX_LAWS = 8

LAW_EXTRACT_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (
                "You extract concrete law, regulation, and policy names cited or implied in snippets. "
                "Prefer official titles, article numbers, act names (e.g. IRA 45Q, 탄소중립기본법, "
                "EU CBAM Regulation). "
                "IMPORTANT: In this project context, 'DAC' means Direct Air Capture (carbon removal), "
                "not the EU tax 'Directive on Administrative Cooperation' or other unrelated DAC acronyms. "
                "Return JSON: {{\"laws\": string[]}}. "
                "Max 8 items. If nothing reliable, {{\"laws\": []}}. "
                "Do not invent names not supported by the text."
            ),
        ),
        ("user", "Search results:\n\n{hits_text}"),
    ]
)


def _law_extract_chain():
    return LAW_EXTRACT_PROMPT | get_chat_model(temperature=0.1, json_mode=True) | JsonOutputParser()


async def extract_law_candidates(hits: list[TavilyHit]) -> tuple[list[str], Optional[str]]:
    if not hits:
        return [], "Tavily 결과 없음"
    if not (settings.OPENAI_API_KEY or "").strip():
        return [], "OPENAI_API_KEY 미설정"

    bundle = "\n\n".join(
        f"### {i}. {h.title}\nURL: {h.url}\n{h.content}"
        for i, h in enumerate(hits, 1)
    )
    try:
        data: Any = await _law_extract_chain().ainvoke({"hits_text": bundle})
    except Exception as exc:  # noqa: BLE001
        logger.warning("law_extract chain failed: %s", exc)
        return [], str(exc)

    if not isinstance(data, dict):
        return [], "법령명 응답 형식 오류"

    laws_raw = data.get("laws")
    if not isinstance(laws_raw, list):
        return [], None

    laws: list[str] = []
    for x in laws_raw:
        if isinstance(x, str) and x.strip():
            laws.append(x.strip())
    return laws[:_MAX_LAWS], None
