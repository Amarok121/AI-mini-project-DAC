from app.schemas.claim import Claim
from app.schemas.agent_result import IndustrialAgentOutput
from app.schemas.source import SourceItem
from .news_agent import run_news
from .patent_agent import run_patent


async def run(claims: list[Claim]) -> IndustrialAgentOutput:
    news = await run_news(claims)
    patents = await run_patent(claims)

    overall_level = _aggregate_level(news, patents)
    mrl_estimate = _estimate_mrl(news, patents)
    summary = _build_summary(news, patents)
    return IndustrialAgentOutput(
        news=news,
        patents=patents,
        overall_level=overall_level,
        mrl_estimate=mrl_estimate,
        summary=summary,
        sources=_build_sources(news, patents),
    )


def _build_sources(news, patents) -> list[SourceItem]:
    items: list[SourceItem] = []
    for news_item in news[:5]:
        items.append(
            SourceItem(
                title=getattr(news_item, 'title', '') or '',
                authors=[],
                year=_extract_year(getattr(news_item, 'published_at', '') or ''),
                source_type='news',
                url=getattr(news_item, 'url', '') or '',
                publisher=getattr(news_item, 'publisher', '') or '',
                raw_text=(getattr(news_item, 'excerpt', '') or getattr(news_item, 'summary', '') or ''),
            )
        )
    for patent in patents[:5]:
        items.append(
            SourceItem(
                title=getattr(patent, 'title', '') or '',
                authors=[],
                year=_extract_year(getattr(patent, 'application_date', '') or ''),
                source_type='patent',
                url=getattr(patent, 'url', '') or None,
                publisher=getattr(patent, 'applicant', '') or '',
                raw_text=(getattr(patent, 'excerpt', '') or getattr(patent, 'summary', '') or ''),
            )
        )
    return [item for item in items if item.title or item.url or item.raw_text]


def _extract_year(value: str) -> int | None:
    digits = ''.join(ch if ch.isdigit() else ' ' for ch in value).split()
    if not digits:
        return None
    try:
        year = int(digits[0])
    except ValueError:
        return None
    return year if 1900 <= year <= 2100 else None


def _build_summary(news, patents) -> str:
    parts: list[str] = []
    if news:
        parts.append(f'뉴스 {len(news)}건을 기반으로 산업 적용 신호를 검토했습니다.')
    if patents:
        parts.append(f'특허 {len(patents)}건을 기반으로 핵심기술 및 출원 상태를 검토했습니다.')
    if not parts:
        return '산업 적용 신호를 확인할 수 있는 뉴스/특허 근거가 부족합니다.'
    return ' '.join(parts)


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
