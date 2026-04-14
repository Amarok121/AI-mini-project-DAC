from __future__ import annotations

import asyncio
import logging

from app.schemas.agent_result import PatentResult
from app.schemas.claim import Claim
from app.services.evaluation import (
    evaluate_patent_core_relevance,
    summarize_patent_evidence,
)
from app.services.patent import (
    fetch_citation_records,
    fetch_patent_text_bundle,
    fetch_prosecution_history,
    pick_first,
    search_publication_patents,
)

logger = logging.getLogger(__name__)


async def run_patent(claims: list[Claim]) -> list[PatentResult]:
    queries = _build_queries(claims)

    try:
        candidates = await _collect_candidates(queries, target_count=5)
        if not candidates:
            return []

        evaluated = await asyncio.gather(
            *[
                _to_result(
                    item=item,
                    query=query,
                    prosecution_items=prosecution_items,
                    citation_items=citation_items,
                )
                for item, query, prosecution_items, citation_items in candidates
            ]
        )
        ranked = sorted(
            evaluated,
            key=lambda result: (
                result.core_score,
                result.status == '등록',
                result.application_date or '',
                result.title,
            ),
            reverse=True,
        )
        return ranked[:5]
    except Exception as exc:
        logger.warning('KIPRIS patent search failed: %s', exc)
        return [_fallback_result(queries[0] if queries else '')]


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
        queries.append(tech_terms[0])
    if claim_terms:
        queries.append(claim_terms[0])
    queries.append('특허 검색')

    deduped: list[str] = []
    for query in queries:
        cleaned = ' '.join(query.split())
        if cleaned and cleaned not in deduped:
            deduped.append(cleaned)
    return deduped


async def _collect_candidates(
    queries: list[str],
    target_count: int = 5,
) -> list[tuple[dict, str, list[dict], list[dict]]]:
    candidates: list[tuple[dict, str, list[dict], list[dict]]] = []
    seen: set[str] = set()

    for query in queries:
        publication_items = await search_publication_patents(query, display=10)
        if not publication_items:
            continue

        for item in publication_items:
            dedupe_key = _patent_dedupe_key(item)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            application_no = _find_application_number(item)
            prosecution_items: list[dict] = []
            citation_items: list[dict] = []

            if application_no:
                prosecution_items = await fetch_prosecution_history(application_no)
                citation_items = await fetch_citation_records(application_no)

            candidates.append((item, query, prosecution_items, citation_items))

        if len(candidates) >= target_count:
            break

    return candidates


async def _to_result(
    item: dict,
    query: str,
    prosecution_items: list[dict],
    citation_items: list[dict],
) -> PatentResult:
    title = pick_first(item, 'title', 'inventionTitle', 'koreanTitle', default='특허 검색 결과')
    applicant = pick_first(item, 'applicantName', 'applicant', 'rightHolder', default='')
    application_date = pick_first(item, 'applicationDate', 'filingDate', default='')
    abstract = _extract_abstract(item)
    application_no = _find_application_number(item)
    claim_text = ''
    if (not abstract or len(abstract.strip()) < 80) and application_no:
        text_bundle = await fetch_patent_text_bundle(application_no)
        claim_text = text_bundle.get('claim_text', '')
        abstract = text_bundle.get('abstract', '') or abstract or claim_text
    status = _normalize_status(item, prosecution_items)
    citation_count = len(citation_items)

    evaluation = await evaluate_patent_core_relevance(
        title=title,
        abstract=abstract,
        query=query,
        status=status,
        citation_count=citation_count,
        application_number=application_no,
    )
    narrative = await summarize_patent_evidence(
        title=title,
        applicant=applicant,
        application_date=application_date,
        status=status,
        query=query,
        abstract=abstract,
        claim_text=claim_text,
        verdict=evaluation.verdict,
        flags=evaluation.flags,
    )
    is_core_tech = evaluation.grade == 'HIGH' and status == '등록'

    combined_flags = list(dict.fromkeys(evaluation.flags + ([narrative.note] if narrative.note else [])))

    return PatentResult(
        title=title or '특허 검색 결과',
        applicant=applicant,
        application_date=application_date,
        status=status,
        excerpt=narrative.excerpt or abstract,
        summary=narrative.summary or abstract or title,
        key_point=narrative.key_point or '',
        is_core_tech=is_core_tech,
        core_score=evaluation.score,
        core_level=evaluation.grade,
        flags=combined_flags,
        verdict=evaluation.verdict,
        reason=(
            f'{evaluation.reason} ({narrative.note})'
            if narrative.note and evaluation.reason
            else (evaluation.reason or narrative.note)
        ),
        evaluation=evaluation,
    )


def _normalize_status(item: dict, prosecution_items: list[dict]) -> str:
    status_text = ' '.join(
        filter(
            None,
            [
                pick_first(item, 'registerStatus', 'status', 'legalStatus'),
                ' '.join(
                    pick_first(step, 'processState', 'step', 'status', 'legalStatus')
                    for step in prosecution_items
                ),
            ],
        )
    ).lower()

    if any(keyword in status_text for keyword in ('등록', '등록결정', 'granted', 'registered')):
        return '등록'
    if any(keyword in status_text for keyword in ('심사', '출원공개', 'pending', 'examination')):
        return '심사중'
    return '출원'


def _find_application_number(item: dict) -> str:
    return pick_first(
        item,
        'applicationNumber',
        'applicationNo',
        'applNo',
        'applicationNoText',
        'docNumber',
        default='',
    )


def _extract_abstract(item: dict) -> str:
    return pick_first(
        item,
        'abstract',
        'summary',
        'koreanAbstract',
        'engAbstract',
        'contents',
        'claimSummary',
        default='',
    )


def _trim_claim_terms(claim_text: str) -> str:
    tokens = [token for token in _tokenize(claim_text) if len(token) > 1]
    filtered = [token for token in tokens if not token.replace(',', '').isdigit()]
    return ' '.join(filtered[:4]) if filtered else claim_text.strip()


def _patent_dedupe_key(item: dict) -> str:
    application_no = _find_application_number(item).strip().lower()
    title = pick_first(item, 'title', 'inventionTitle', 'koreanTitle', default='').strip().lower()
    applicant = pick_first(item, 'applicantName', 'applicant', 'rightHolder', default='').strip().lower()
    return application_no or f'{title}|{applicant}'


def _fallback_result(query: str) -> PatentResult:
    return PatentResult(
        title=f'KIPRIS 검색 실패: {query[:40]}' if query else 'KIPRIS 검색 실패',
        applicant='fallback',
        application_date='',
        status='출원',
        is_core_tech=False,
        summary='KIPRIS 특허 검색 실패',
        reason='KIPRIS 특허 검색 실패',
    )


def _tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for raw in (text or '').replace('/', ' ').replace('-', ' ').split():
        cleaned = ''.join(ch for ch in raw if ch.isalnum() or '\uac00' <= ch <= '\ud7a3')
        if cleaned:
            tokens.append(cleaned.lower())
    return tokens
