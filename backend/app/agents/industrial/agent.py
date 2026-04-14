from app.schemas.claim import Claim
from app.schemas.agent_result import IndustrialAgentOutput
from .news_agent import run_news
from .patent_agent import run_patent


async def run(claims: list[Claim]) -> IndustrialAgentOutput:
    news = await run_news(claims)
    patents = await run_patent(claims)

    overall_level = _aggregate_level(news, patents)
    mrl_estimate = _estimate_mrl(news, patents)
    return IndustrialAgentOutput(
        news=news,
        patents=patents,
        overall_level=overall_level,
        mrl_estimate=mrl_estimate,
        summary='',
    )


def _aggregate_level(news, patents) -> str:
    news_scores = [item.craap_score for item in news if getattr(item, 'craap_score', None) is not None]
    news_avg = sum(news_scores) / len(news_scores) if news_scores else 0.0

    if patents:
        patent_signal = 0.8 if any(p.is_core_tech and p.status == '등록' for p in patents) else 0.55
    else:
        patent_signal = 0.25

    combined = (news_avg * 0.6) + (patent_signal * 0.4)

    if combined >= 0.75:
        return 'HIGH'
    if combined >= 0.5:
        return 'MED'
    return 'LOW'


def _estimate_mrl(news, patents) -> str:
    has_registered_core_patent = any(p.is_core_tech and p.status == '등록' for p in patents)
    has_any_patent = bool(patents)
    news_avg = _average_news_score(news)

    if has_registered_core_patent and news_avg >= 0.7:
        return 'MRL 5~6'
    if has_any_patent and news_avg >= 0.5:
        return 'MRL 3~4'
    if news_avg >= 0.7:
        return 'MRL 2~3'
    return 'MRL 1~3'


def _average_news_score(news) -> float:
    scores = [item.craap_score for item in news if getattr(item, 'craap_score', None) is not None]
    return sum(scores) / len(scores) if scores else 0.0

