"""
Tavily 검색: 규제·정책 1단계 탐색 (설계: 웹서치 → 법령명 → 정부 포털 원문).

CCU/DAC·탄소 인센티브 등 클레임과 맞도록 `build_regulatory_query`에서 질의를 구성한다.
공식 도메인 필터는 인센티브·환경 규제 출처를 노린다.

환경 변수: `TAVILY_API_KEY` (app.core.config.settings)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate

from app.core.config import settings
from app.agents.langchain_setup import get_chat_model

if TYPE_CHECKING:
    from app.schemas.claim import Claim

logger = logging.getLogger(__name__)

# 규제 원문·공고에 가까운 도메인 (필요 시 조정)
_DEFAULT_INCLUDE_DOMAINS: tuple[str, ...] = (
    "law.go.kr",
    "me.go.kr",
    "federalregister.gov",
    "energy.gov",
    "epa.gov",
    "fda.gov",
    "eur-lex.europa.eu",
    "echa.europa.eu",
    "ec.europa.eu",
)


@dataclass(frozen=True)
class TavilyHit:
    title: str
    url: str
    content: str


_PIPELINE_QUERY_SCHEMA_HINT = """{
  "query": string
}"""

_PIPELINE_QUERY_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (
                "You craft a single web-search query (Korean/English mixed OK) for finding official regulatory, "
                "permitting, and incentive information. Output JSON only.\n"
                "- Prioritize environment/climate Direct Air Capture (DAC) and carbon capture/removal context.\n"
                "- Include CCU/CCUS/CCS/CDR, sequestration, permitting, 45Q, Class VI/UIC, NEPA keywords only if relevant.\n"
                "- Avoid unrelated acronyms: here 'DAC' means Direct Air Capture, not EU tax 'Directive on Administrative Cooperation' (DAC6/7).\n"
                "- Keep it short (<= 240 chars) but specific.\n"
                f"Schema: {_PIPELINE_QUERY_SCHEMA_HINT}"
            ),
        ),
        ("user", "{claims_block}"),
    ]
)


def _pipeline_query_chain():
    return _PIPELINE_QUERY_PROMPT | get_chat_model(temperature=0.2, json_mode=True) | JsonOutputParser()


def _claims_block_for_query(claims: list[Claim]) -> str:
    lines: list[str] = []
    for c in claims[:8]:
        lines.append(f"- 기술: {c.technology} | 주장: {c.claim} | 적용: {c.application}")
    return "\n".join(lines) if lines else "- (클레임 없음)"


def build_regulatory_query(claims: list[Claim]) -> str:
    """Claim에서 Tavily 검색용 영·한 혼합 쿼리 문자열 생성."""
    chunks: list[str] = []
    for c in claims:
        chunks.append(f"{c.technology} {c.application} {c.claim}".strip())
    base = " ".join(chunks) if chunks else "environmental regulation policy"
    # 공식 문서 위주로 좁히기 위한 힌트 (Tavily가 질의와 함께 해석)
    return f"{base} regulation law policy incentive compliance"


def build_pipeline_tavily_query(claims: list[Claim]) -> str:
    """법령·인센티브 탐색용 확장 쿼리 (포털 fetch 파이프라인 1단계)."""
    chunks: list[str] = []
    for c in claims:
        chunks.append(f"{c.technology} {c.application}".strip())
    tech = " ".join(chunks) if chunks else "carbon capture"
    # 규제 탐색은 DAC(Direct Air Capture) 단독 키워드만으로는 누락이 생기기 쉬워
    # CCU/CCUS/저장/인허가/세제/환경평가 프레임까지 넓혀서 검색한다.
    expand = (
        "CCU CCUS CCS CDR carbon removal "
        "direct air capture DAC DACCS "
        "carbon capture sequestration storage "
        "45Q IRS tax credit "
        "Class VI UIC EPA "
        "NEPA permitting "
        "탄소포집 탄소저장 이산화탄소 지중저장 탄소제거 "
        "규제 법령 인허가 허가 인센티브 세액공제 환경영향평가"
    )
    return f"{tech} {expand} environmental regulation policy"


async def build_pipeline_tavily_query_llm(claims: list[Claim]) -> str:
    """
    LLM 기반: 입력 클레임에 맞춘 Tavily 파이프라인 쿼리 생성.
    실패 시 휴리스틱(`build_pipeline_tavily_query`)로 폴백.
    """
    if not (settings.OPENAI_API_KEY or "").strip():
        return build_pipeline_tavily_query(claims)
    try:
        data = await _pipeline_query_chain().ainvoke({"claims_block": _claims_block_for_query(claims)})
    except Exception as exc:  # noqa: BLE001
        logger.warning("regulatory query LLM failed: %s", exc)
        return build_pipeline_tavily_query(claims)

    if not isinstance(data, dict):
        return build_pipeline_tavily_query(claims)
    q = str(data.get("query") or "").strip()
    if not q:
        return build_pipeline_tavily_query(claims)
    return q[:240]

def _search_sync(query: str, max_results: int) -> list[TavilyHit]:
    if not (settings.TAVILY_API_KEY or "").strip():
        return []

    try:
        from tavily import TavilyClient
    except ImportError:
        logger.warning("tavily 패키지가 없습니다. pip install tavily-python")
        return []

    client = TavilyClient(api_key=settings.TAVILY_API_KEY)
    raw = client.search(
        query=query,
        search_depth="advanced",
        max_results=max_results,
        include_domains=list(_DEFAULT_INCLUDE_DOMAINS),
    )
    results = raw.get("results") or []
    out: list[TavilyHit] = []
    for r in results:
        title = (r.get("title") or "").strip() or "(제목 없음)"
        url = (r.get("url") or "").strip()
        content = (r.get("content") or r.get("raw_content") or "").strip()
        if url:
            out.append(TavilyHit(title=title, url=url, content=content[:4000]))
    return out


async def search_regulatory_context(
    query: str,
    *,
    max_results: int = 8,
) -> list[TavilyHit]:
    """
    Tavily 검색 (동기 SDK를 이벤트 루프 블로킹 없이 실행).
    키가 없으면 빈 리스트.
    """
    return await asyncio.to_thread(_search_sync, query, max_results)


async def search_regulations_pipeline(claims: list[Claim], *, max_results: int = 10) -> list[TavilyHit]:
    """파이프라인 전용: 확장 쿼리 + 동일 공식 도메인 필터."""
    q = await build_pipeline_tavily_query_llm(claims)
    return await search_regulatory_context(q, max_results=max_results)
