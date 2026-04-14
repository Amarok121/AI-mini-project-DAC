from __future__ import annotations

import asyncio
import logging

from app.schemas.agent_result import NewsResult
from app.schemas.claim import Claim
from app.services.evaluation import evaluate_news_credibility, summarize_news_evidence
from app.services.news import fetch_news_article_content, fetch_news_article_text, search_naver_news

logger = logging.getLogger(__name__)


async def run_news(claims: list[Claim]) -> list[NewsResult]:
    queries = _build_queries(claims)

    try:
        candidates = await _collect_candidates(queries, target_count=20, attempts=1)
        if not candidates:
            return []

        evaluated = await asyncio.gather(
            *[
                _to_result(item, query, support_count=support_count)
                for item, query, support_count in candidates
            ]
        )
        ranked = sorted(
            evaluated,
            key=lambda result: (
                result.craap_score,
                result.published_at or '',
                result.title,
            ),
            reverse=True,
        )
        enriched = await _enrich_top_results(ranked[:15])
        fulltext_first = [item for item in enriched if _has_fulltext_evidence(item)]
        fallback_items = [item for item in enriched if not _has_fulltext_evidence(item)]
        if fulltext_first:
            return (fulltext_first + fallback_items)[:5]

        # 본문 확보 실패 시 최대 3회까지 재탐색한다.
        retried_candidates = await _collect_candidates(queries, target_count=30, attempts=3)
        if retried_candidates:
            retried_evaluated = await asyncio.gather(
                *[
                    _to_result(item, query, support_count=support_count)
                    for item, query, support_count in retried_candidates
                ]
            )
            retried_ranked = sorted(
                retried_evaluated,
                key=lambda result: (
                    result.craap_score,
                    result.published_at or '',
                    result.title,
                ),
                reverse=True,
            )
            retried_enriched = await _enrich_top_results(retried_ranked[:20])
            retried_fulltext = [item for item in retried_enriched if _has_fulltext_evidence(item)]
            retried_fallback = [item for item in retried_enriched if not _has_fulltext_evidence(item)]
            if retried_fulltext:
                return (retried_fulltext + retried_fallback)[:5]

        return [_no_fulltext_result(queries[0] if queries else '')]
    except Exception as exc:
        logger.warning('Naver news search failed: %s', exc)
        return [_fallback_result(str(exc), queries[0] if queries else '')]


def _build_queries(claims: list[Claim]) -> list[str]:
    tech_terms: list[str] = []
    app_terms: list[str] = []
    claim_terms: list[str] = []

    for claim in claims:
        if claim.technology and claim.technology.strip():
            tech_terms.append(claim.technology.strip())
        if claim.application and claim.application.strip():
            app_terms.append(claim.application.strip())
        if claim.claim and claim.claim.strip():
            claim_terms.append(_trim_claim_terms(claim.claim))

    queries: list[str] = []
    if tech_terms:
        queries.append(' '.join(dict.fromkeys(tech_terms[:3])))
    if tech_terms and app_terms:
        queries.append(' '.join(dict.fromkeys([*tech_terms[:2], *app_terms[:2]])))
    if tech_terms and claim_terms:
        queries.append(' '.join(dict.fromkeys([tech_terms[0], claim_terms[0]])))
    if tech_terms:
        queries.append(_keyword_variant(tech_terms[0]))

    queries.append('DAC')
    queries.append('탄소 포집')
    queries.append('direct air capture')

    deduped: list[str] = []
    for query in queries:
        cleaned = ' '.join(query.split())
        if cleaned and cleaned not in deduped:
            deduped.append(cleaned)
    return deduped


def _trim_claim_terms(claim_text: str) -> str:
    tokens = [token for token in _tokenize(claim_text) if len(token) > 1]
    filtered = [token for token in tokens if not token.replace(',', '').isdigit()]
    return ' '.join(filtered[:4]) if filtered else claim_text.strip()


def _keyword_variant(text: str) -> str:
    lowered = text.lower()
    variants = {
        'dac 직접공기포집': '직접공기포집',
        'direct air capture': 'direct air capture',
    }
    for key, value in variants.items():
        if key in lowered:
            return value
    return text


async def _collect_candidates(
    queries: list[str],
    target_count: int = 5,
    attempts: int = 1,
) -> list[tuple[dict, str, int]]:
    candidates: list[tuple[dict, str, int]] = []
    seen: set[str] = set()
    start_offsets = [1, 11, 21][: max(1, attempts)]

    for query in queries:
        for start in start_offsets:
            raw_items = await search_naver_news(query, display=10, start=start)
            if not raw_items:
                continue

            support_count = len(raw_items)
            for item in raw_items:
                dedupe_key = _news_dedupe_key(item)
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                candidates.append((item, query, support_count))

            if len(candidates) >= target_count:
                break
        if len(candidates) >= target_count:
            break

    return candidates


async def _to_result(item: dict, query: str, support_count: int) -> NewsResult:
    title = item.get('title', '').strip() or '네이버 뉴스 검색 결과'
    provider = item.get('provider', '').strip() or 'naver.com'
    description = item.get('description', '').strip()
    published_at = item.get('published_at', '').strip()
    origin_url = item.get('origin_url', '').strip()
    naver_url = item.get('naver_url', '').strip()
    url = item.get('url', '').strip() or origin_url or naver_url

    evaluation = await evaluate_news_credibility(
        title=title,
        provider=provider,
        published_at=published_at,
        query=query,
        description=description,
        support_count=support_count,
    )
    return NewsResult(
        title=title,
        publisher=provider,
        published_at=published_at,
        url=url,
        excerpt=description,
        summary=description,
        craap_score=evaluation.score,
        craap_level=evaluation.grade,
        flags=evaluation.flags,
        verdict=evaluation.verdict,
        reason=evaluation.reason,
        evaluation=evaluation,
    )


async def _enrich_top_results(results: list[NewsResult]) -> list[NewsResult]:
    enriched: list[NewsResult] = []
    for result in results:
        article_text = ''
        note = ''
        try:
            content = await fetch_news_article_content(result.url)
            article_text = content.get('text', '')
            trace = content.get('trace', '')
            if trace and _trace_needs_note(trace):
                note = f'본문 추출 경로: {trace}'
        except Exception as exc:
            # 구형 함수 fallback: 팀원 코드와의 호환 목적
            try:
                article_text = await fetch_news_article_text(result.url)
                note = '본문 추출 경로: 구형 fetch 함수 fallback 사용'
            except Exception:
                note = f'본문 추출 실패: {exc}'

        if article_text.strip():
            narrative = await summarize_news_evidence(
                title=result.title,
                provider=_news_publisher(result),
                published_at=result.published_at,
                query=_guess_query_from_result(result),
                description=result.excerpt or result.summary,
                article_text=article_text,
                verdict=result.verdict,
                flags=result.flags,
            )
            result.excerpt = narrative.excerpt or result.excerpt
            result.summary = narrative.summary or result.summary
            if narrative.note and _should_attach_narrative_note(narrative.note, article_text):
                note = narrative.note if not note else f'{note}; {narrative.note}'
        else:
            result.summary = _fallback_news_summary(result)
            if not note:
                note = '본문 미확보(메타데이터 기반 요약)'

        if note:
            if note not in result.flags:
                result.flags.append(note)
            if result.reason:
                result.reason = f'{result.reason} ({note})'
            else:
                result.reason = note

        enriched.append(result)
    return enriched


def _fallback_result(error_message: str, query: str) -> NewsResult:
    title = '네이버 뉴스 검색 실패'
    if query:
        title = f'{title}: {query[:40]}'

    return NewsResult(
        title=title,
        publisher='fallback',
        published_at='',
        url='',
        excerpt=error_message,
        summary=error_message,
        craap_score=0.1,
        craap_level='LOW',
        reason=error_message,
    )


def _no_fulltext_result(query: str) -> NewsResult:
    title = '본문 확보 가능한 뉴스 없음'
    if query:
        title = f'{title}: {query[:40]}'
    return NewsResult(
        title=title,
        publisher='fallback',
        published_at='',
        url='',
        excerpt='검색은 성공했지만 본문 추출 가능한 기사 확보에 실패했습니다.',
        summary='본문 확보 가능한 기사 부족으로 뉴스 근거를 생성하지 못했습니다. 다른 키워드 또는 기간으로 재탐색이 필요합니다.',
        craap_score=0.2,
        craap_level='LOW',
        flags=['본문 확보 실패'],
        verdict='근거 부족',
        reason='모든 후보가 본문 미확보 상태라 description 기반 요약을 제외했습니다.',
    )


def _tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for raw in text.replace('/', ' ').replace('-', ' ').split():
        cleaned = ''.join(ch for ch in raw if ch.isalnum() or '\uac00' <= ch <= '\ud7a3')
        if cleaned:
            tokens.append(cleaned.lower())
    return tokens


def _news_dedupe_key(item: dict) -> str:
    title = (item.get('title', '') or '').strip().lower()
    url = (item.get('url', '') or '').strip().lower()
    provider = (item.get('provider', '') or '').strip().lower()
    return f'{title}|{url}|{provider}'


def _guess_query_from_result(result: NewsResult) -> str:
    tokens = [token for token in _tokenize(result.title) if len(token) > 1]
    if tokens:
        return ' '.join(tokens[:4])
    return result.title


def _fallback_news_summary(result: NewsResult) -> str:
    source_text = result.excerpt or result.summary or result.title
    return (
        f'{_news_publisher(result)} 기사 "{result.title}"은 {source_text}를 다룬다. '
        f'기술 검증 관점에서는 {result.verdict or "추가 확인이 필요하다"}.'
    ).strip()


def _trace_needs_note(trace: str) -> bool:
    lowered = (trace or '').lower()
    return any(marker in lowered for marker in ('실패:', '본문부족:', '최종오류:', 'fallback'))


def _should_attach_narrative_note(note: str, article_text: str) -> bool:
    lowered = (note or '').lower()
    text_len = len((article_text or '').strip())

    # 본문이 충분히 확보된 경우, "description 보조"성 안내는 노이즈이므로 숨긴다.
    description_markers = (
        'description',
        '보조로 활용',
        'description 기반',
    )
    if any(marker in lowered for marker in description_markers) and text_len >= 350:
        return False
    return True


def _has_fulltext_evidence(result: NewsResult) -> bool:
    red_flags = (
        '본문 미확보',
        '본문 추출 실패',
        '본문 추출 경로:',
        'description 기반',
        '메타데이터 기반 요약',
    )
    all_text = ' '.join([*(result.flags or []), result.reason or '']).lower()
    return not any(marker.lower() in all_text for marker in red_flags)


def _news_publisher(result: NewsResult) -> str:
    return getattr(result, 'publisher', '') or getattr(result, 'provider', '') or 'unknown'
