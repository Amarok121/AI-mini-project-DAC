from __future__ import annotations

import json
import logging
from functools import lru_cache
from datetime import date, datetime
from typing import Any, Literal

from openai import AsyncOpenAI

from app.core.config import settings
from app.schemas.agent_result import (
    NewsEvaluation,
    NewsEvaluationBreakdown,
    NewsEvidenceNarrative,
    PatentEvaluation,
    PatentEvaluationBreakdown,
    PatentEvidenceNarrative,
)

logger = logging.getLogger(__name__)

NEWS_EVAL_MODEL = 'gpt-4o'
PATENT_EVAL_MODEL = 'gpt-4o'


async def evaluate_news_credibility(
    *,
    title: str,
    provider: str,
    published_at: str,
    query: str,
    description: str,
    support_count: int = 1,
) -> NewsEvaluation:
    payload = {
        'title': title,
        'provider': provider,
        'published_at': published_at,
        'query': query,
        'description': description,
        'support_count': support_count,
        'criteria': {
            'currency': {
                'meaning': '언제 발행됐는가',
                'score_rules': {
                    '<=30_days': 1.0,
                    '<=180_days': 0.8,
                    '<=365_days': 0.6,
                    '<=730_days': 0.4,
                    '>730_days': 0.2,
                },
            },
            'relevance': {
                'meaning': '검증 대상 기술과 얼마나 관련 있는가',
            },
            'authority': {
                'meaning': '어떤 매체인가, 기자 전문성이 있는가',
                'tier_1': ['연합뉴스', 'Reuters', 'Nature', 'Nature News', 'Science', '조선일보', '중앙일보', '동아일보'],
                'tier_2': ['동아사이언스', '전자신문', '에너지경제', '한국경제', '매일경제', 'ZDNet', '서울경제', 'SBS Biz'],
                'tier_3': ['일반 온라인 매체', '지역지', '산업 기사', '전문성 낮은 온라인 매체'],
                'tier_4': ['출처 불명', '블로그', '커뮤니티', '펌글'],
                'judgement_rule': '목록은 예시이며, 목록에 없는 매체는 공신력, 독립 취재 여부, 기술 전문성, 보도자료 의존도를 기준으로 가장 가까운 tier로 분류',
            },
            'accuracy': {
                'meaning': '복수 소스 교차 확인, 1차 소스 인용 여부',
                'support_count_rules': {
                    '>=5': 1.0,
                    '2_to_4': 0.7,
                    '1': 0.3,
                },
                'adjustments': {
                    'official_source_or_primary_citation': '+0.2',
                    'phrases_like_according_to_insiders': '-0.2',
                    'press_release_based': '-0.3',
                },
            },
            'purpose': {
                'meaning': '독립 취재인가, 보도자료 기반인가, 편향이 있는가',
                'score_rules': {
                    'independent_reporting': 1.0,
                    'company_press_plus_independent_review': 0.7,
                    'press_release_based': 0.4,
                    'promotional': 0.2,
                },
            },
            'weights': {
                'currency': 0.10,
                'relevance': 0.15,
                'authority': 0.20,
                'accuracy': 0.30,
                'purpose': 0.25,
            },
            'grade_thresholds': {
                'HIGH': '>=0.75',
                'MED': '0.50~0.75',
                'LOW': '<0.50',
            },
        },
        'output_schema': {
            'score': 'float between 0 and 1',
            'grade': 'HIGH | MED | LOW',
            'breakdown': {
                'currency': 'float between 0 and 1',
                'relevance': 'float between 0 and 1',
                'authority': 'float between 0 and 1',
                'accuracy': 'float between 0 and 1',
                'purpose': 'float between 0 and 1',
            },
            'flags': 'list[str]',
            'verdict': 'str',
            'reason': 'str',
        },
    }

    llm_result = await _call_llm_json(
        model=NEWS_EVAL_MODEL,
        system_prompt=_news_system_prompt(),
        payload=payload,
    )
    if llm_result is not None:
        try:
            return _normalize_news_result(NewsEvaluation.model_validate(llm_result))
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.warning('News LLM evaluation parsing failed: %s', exc)

    return _fallback_news_evaluation(title=title, provider=provider, published_at=published_at, query=query, description=description, support_count=support_count)


async def evaluate_patent_core_relevance(
    *,
    title: str,
    abstract: str,
    query: str,
    status: str,
    citation_count: int,
    application_number: str = '',
) -> PatentEvaluation:
    payload = {
        'title': title,
        'abstract': abstract,
        'query': query,
        'status': status,
        'citation_count': citation_count,
        'application_number': application_number,
        'criteria': {
            'search_match': {
                'meaning': '기술명/검색어와의 일치도',
            },
            'legal_status': {
                'meaning': '등록/심사중/출원 상태가 핵심기술 판단에 미치는 영향',
            },
            'citation_signal': {
                'meaning': '인용문헌과 선행기술 연결 정도',
            },
            'specificity': {
                'meaning': '특허가 기술의 핵심 구현인지 주변기술인지',
            },
            'weights': {
                'search_match': 0.35,
                'legal_status': 0.25,
                'citation_signal': 0.25,
                'specificity': 0.15,
            },
            'grade_thresholds': {
                'HIGH': '>=0.75',
                'MED': '0.50~0.75',
                'LOW': '<0.50',
            },
            'verdict_examples': {
                '핵심기술 가능성 높음': 'score가 높고 등록 상태이며 구체적 구현을 다루는 경우',
                '관련기술 또는 핵심기술 후보': '관련성은 높지만 핵심성은 아직 확정적이지 않은 경우',
                '주변기술 가능성 높음': '검색어 일치나 구체성이 약한 경우',
            },
        },
        'output_schema': {
            'score': 'float between 0 and 1',
            'grade': 'HIGH | MED | LOW',
            'breakdown': {
                'search_match': 'float between 0 and 1',
                'legal_status': 'float between 0 and 1',
                'citation_signal': 'float between 0 and 1',
                'specificity': 'float between 0 and 1',
            },
            'flags': 'list[str]',
            'verdict': 'str',
            'reason': 'str',
        },
    }

    llm_result = await _call_llm_json(
        model=PATENT_EVAL_MODEL,
        system_prompt=_patent_system_prompt(),
        payload=payload,
    )
    if llm_result is not None:
        try:
            return _normalize_patent_result(PatentEvaluation.model_validate(llm_result))
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.warning('Patent LLM evaluation parsing failed: %s', exc)

    return _fallback_patent_evaluation(
        title=title,
        abstract=abstract,
        query=query,
        status=status,
        citation_count=citation_count,
        application_number=application_number,
    )


async def summarize_news_evidence(
    *,
    title: str,
    provider: str,
    published_at: str,
    query: str,
    description: str,
    article_text: str,
    verdict: str,
    flags: list[str],
) -> NewsEvidenceNarrative:
    payload = {
        'title': title,
        'provider': provider,
        'published_at': published_at,
        'query': query,
        'description': description,
        'article_text': article_text[:12000],
        'verdict': verdict,
        'flags': flags,
        'instructions': [
            '기사 전체를 요약하지 말고, 기술 검증에 직접 필요한 내용만 추려 요약할 것.',
            '기술명, 성능, 실증 단계, 규모, 조건, 한계, 기업 발표 여부, 독립 검증 여부에 집중할 것.',
            '홍보성 수사나 기사 흐름 설명은 최소화할 것.',
            'summary는 2~4문장 정도로, excerpt는 본문에서 가장 검증 가치가 높은 문장 1~2개로 구성할 것.',
            '본문 추출이 부정확하면 description을 보조로 활용하되 note에 한계를 적을 것.',
        ],
    }

    llm_result = await _call_llm_json(
        model=NEWS_EVAL_MODEL,
        system_prompt=_news_summary_system_prompt(),
        payload=payload,
    )
    if llm_result is not None:
        try:
            result = NewsEvidenceNarrative.model_validate(llm_result)
            result.summary = result.summary.strip()
            result.excerpt = result.excerpt.strip()
            result.note = result.note.strip()
            return result
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.warning('News narrative parsing failed: %s', exc)

    fallback_excerpt = _shorten_text(article_text or description)
    fallback_summary = (
        f'{provider} 기사 "{title}"은 {fallback_excerpt or description or "관련 기술 소식을 다룬다."} '
        f'기술 검증 관점에서 {verdict}로 해석된다.'
    ).strip()
    return NewsEvidenceNarrative(
        summary=fallback_summary,
        excerpt=fallback_excerpt or description,
        note='LLM 요약 실패 또는 본문 추출 제한으로 description 기반 대체 요약을 사용함',
    )


async def summarize_patent_evidence(
    *,
    title: str,
    applicant: str,
    application_date: str,
    status: str,
    query: str,
    abstract: str,
    claim_text: str = '',
    verdict: str,
    flags: list[str],
) -> PatentEvidenceNarrative:
    evidence_text = (claim_text or '').strip() or (abstract or '').strip()
    payload = {
        'title': title,
        'applicant': applicant,
        'application_date': application_date,
        'status': status,
        'query': query,
        'abstract': abstract[:12000],
        'claim_text': claim_text[:12000],
        'evidence_text': evidence_text[:12000],
        'verdict': verdict,
        'flags': flags,
        'instructions': [
            '특허 요약은 등록상태/일치도 설명이 아니라, 특허가 제안하는 기술 구성과 작동 방식을 중심으로 작성할 것.',
            'claim_text가 있으면 abstract보다 우선해서 해석할 것.',
            'summary는 4~6문장으로, 문제정의→핵심구성→작동방식→적용맥락→검증한계 순으로 작성할 것.',
            'excerpt는 evidence_text(청구항/초록)에서 검증 가치가 높은 핵심 문장 1~2개를 추출할 것.',
            'key_point는 보고서에서 바로 쓰는 1문장 결론으로 작성할 것.',
            '"초록이 제공되지 않았습니다" 같은 문구를 excerpt에 쓰지 말 것. 문장이 없으면 title/query 기반 핵심기술 설명 문장을 생성할 것.',
            'flags 문구를 note로 반복하지 말 것.',
        ],
    }

    llm_result = await _call_llm_json(
        model=PATENT_EVAL_MODEL,
        system_prompt=_patent_summary_system_prompt(),
        payload=payload,
    )
    if llm_result is not None:
        try:
            result = PatentEvidenceNarrative.model_validate(llm_result)
            result.summary = result.summary.strip()
            result.excerpt = result.excerpt.strip()
            result.key_point = result.key_point.strip()
            result.note = result.note.strip()
            return _normalize_patent_narrative(
                result=result,
                title=title,
                query=query,
                evidence_text=evidence_text,
            )
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.warning('Patent narrative parsing failed: %s', exc)

    abstract_excerpt = _shorten_text(evidence_text, limit=420)
    fallback_summary = (
        f'특허 "{title}"은 {abstract_excerpt or "질의 기술과 관련된 장치/공정 구성을 제안한다."} '
        f'핵심은 {query or "해당 기술"}의 구현 구조와 운전 단계에 관한 것으로 해석된다. '
        f'출원인 {applicant or "미상"}, 출원일 {application_date or "미상"}, 법적 상태 {status}다. '
        f'현재 판정은 "{verdict}"이며, 보고서에서는 실증/양산 근거와 함께 교차 검증이 필요하다.'
    ).strip()
    fallback_key_point = (
        f'{title}은 {status} 단계에서 {query or "질의 기술"}의 구현 가능성을 보여주는 특허 후보다.'
    ).strip()
    return PatentEvidenceNarrative(
        summary=fallback_summary,
        excerpt=abstract_excerpt or f'{title}은 {query or "질의 기술"} 관련 핵심 구성/공정을 다루는 특허다.',
        key_point=fallback_key_point,
        note='LLM 요약 실패로 rule-based 대체 요약을 사용함',
    )


async def _call_llm_json(*, model: str, system_prompt: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    if not settings.OPENAI_API_KEY:
        logger.info('OPENAI_API_KEY is not configured; using fallback evaluation')
        return None

    client = _get_client()
    try:
        response = await client.chat.completions.create(
            model=model,
            temperature=0,
            response_format={'type': 'json_object'},
            messages=[
                {'role': 'system', 'content': system_prompt},
                {
                    'role': 'user',
                    'content': json.dumps(payload, ensure_ascii=False, indent=2),
                },
            ],
        )
        content = response.choices[0].message.content or '{}'
        return json.loads(content)
    except Exception as exc:  # pragma: no cover - external failure fallback
        logger.warning('LLM evaluation request failed: %s', exc)
        return None


@lru_cache(maxsize=1)
def _get_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


def _news_system_prompt() -> str:
    return (
        '당신은 기술 검증 보고서용 뉴스 신뢰도 평가자입니다.\n'
        '반드시 주어진 평가 기준만 사용해서 뉴스 기사 1건의 신뢰도를 평가하세요.\n'
        '한국어로 답변하되, 출력은 오직 JSON 객체만 허용됩니다.\n'
        '절대 부가 설명, 마크다운, 코드 블록을 넣지 마세요.\n'
        '\n'
        '평가 기준:\n'
        '- Currency: 발행 시점이 얼마나 최근인지 평가\n'
        '- Relevance: 검증 대상 기술과 얼마나 직접 관련이 있는지 평가\n'
        '- Authority: 매체 신뢰도와 권위를 평가. 예시 목록에 없으면 공신력, 독립 취재 여부, 기술 전문성, 보도자료 의존도를 기준으로 가장 가까운 tier로 분류\n'
        '- Accuracy: 복수 소스 교차 확인, 1차 소스 인용 여부, 보도자료 의존성 평가\n'
        '- Purpose: 독립 취재인지, 보도자료/홍보성인지 평가\n'
        '- 가중치: currency 0.10, relevance 0.15, authority 0.20, accuracy 0.30, purpose 0.25\n'
        '- 등급: score >= 0.75면 HIGH, 0.50~0.75면 MED, 그 미만이면 LOW\n'
        '\n'
        '반드시 아래 키만 가진 JSON 객체를 반환하세요:\n'
        '{\n'
        '  "score": 0.0,\n'
        '  "grade": "HIGH|MED|LOW",\n'
        '  "breakdown": {\n'
        '    "currency": 0.0,\n'
        '    "relevance": 0.0,\n'
        '    "authority": 0.0,\n'
        '    "accuracy": 0.0,\n'
        '    "purpose": 0.0\n'
        '  },\n'
        '  "flags": ["..."],\n'
        '  "verdict": "...",\n'
        '  "reason": "..."\n'
        '}\n'
        '\n'
        'score와 breakdown 값은 반드시 0과 1 사이의 숫자여야 합니다.\n'
    )


def _patent_system_prompt() -> str:
    return (
        '당신은 기술 검증 보고서용 특허 핵심성 평가자입니다.\n'
        '반드시 주어진 평가 기준만 사용해서 특허 1건의 핵심 기술 관련성을 평가하세요.\n'
        '한국어로 답변하되, 출력은 오직 JSON 객체만 허용됩니다.\n'
        '절대 부가 설명, 마크다운, 코드 블록을 넣지 마세요.\n'
        '\n'
        '평가 기준:\n'
        '- Search match: 기술명/검색어와 특허 제목/초록의 일치도\n'
        '- Legal status: 등록/심사중/출원 상태가 핵심기술 판단에 미치는 영향\n'
        '- Citation signal: 인용문헌과 선행기술 연결 정도\n'
        '- Specificity: 특허가 핵심 구현인지 주변기술인지\n'
        '- 가중치: search_match 0.35, legal_status 0.25, citation_signal 0.25, specificity 0.15\n'
        '- 등급: score >= 0.75면 HIGH, 0.50~0.75면 MED, 그 미만이면 LOW\n'
        '\n'
        '반드시 아래 키만 가진 JSON 객체를 반환하세요:\n'
        '{\n'
        '  "score": 0.0,\n'
        '  "grade": "HIGH|MED|LOW",\n'
        '  "breakdown": {\n'
        '    "search_match": 0.0,\n'
        '    "legal_status": 0.0,\n'
        '    "citation_signal": 0.0,\n'
        '    "specificity": 0.0\n'
        '  },\n'
        '  "flags": ["..."],\n'
        '  "verdict": "...",\n'
        '  "reason": "..."\n'
        '}\n'
        '\n'
        'score와 breakdown 값은 반드시 0과 1 사이의 숫자여야 합니다.\n'
    )


def _patent_summary_system_prompt() -> str:
    return (
        '당신은 기술 검증 보고서용 특허 요약자입니다.\n'
        '반드시 제공된 특허 메타데이터와 evidence_text(청구항/초록)만 사용해서 검증용 요약을 작성하세요.\n'
        '한국어로 답변하되, 출력은 오직 JSON 객체만 허용됩니다.\n'
        '절대 부가 설명, 마크다운, 코드 블록을 넣지 마세요.\n'
        '\n'
        '요약 규칙:\n'
        '- claim_text가 있으면 abstract보다 우선 해석하세요.\n'
        '- summary는 4~6문장으로 작성하고, 문제정의/핵심구성/작동방식/적용맥락/검증한계를 포함하세요.\n'
        '- excerpt는 evidence_text에서 검증 가치가 높은 핵심 문장 1~2개를 추출하세요.\n'
        '- key_point는 보고서용 한 줄 결론으로 작성하세요.\n'
        '- excerpt에 "초록이 제공되지 않았습니다" 같은 문구를 쓰지 마세요.\n'
        '- note에는 요약 경로 메모만 기록하고, 정보부족 문구를 반복하지 마세요.\n'
        '\n'
        '반드시 아래 키만 가진 JSON 객체를 반환하세요:\n'
        '{\n'
        '  "summary": "...",\n'
        '  "excerpt": "...",\n'
        '  "key_point": "...",\n'
        '  "note": "..."\n'
        '}\n'
    )


def _news_summary_system_prompt() -> str:
    return (
        '당신은 기술 검증 보고서용 뉴스 본문 요약자입니다.\n'
        '반드시 제공된 본문/설명만 사용해서 기사 1건의 검증용 요약을 작성하세요.\n'
        '중요한 것은 기사 전체 요약이 아니라, 기술 검증에 유의미한 사실만 추리는 것입니다.\n'
        '한국어로 답변하되, 출력은 오직 JSON 객체만 허용됩니다.\n'
        '절대 부가 설명, 마크다운, 코드 블록을 넣지 마세요.\n'
        '\n'
        '요약 규칙:\n'
        '- 기술명, 성능 수치, 실증 단계, 규모, 조건, 한계, 기업 발표 여부, 독립 검증 여부를 우선 요약\n'
        '- 홍보성 수사, 반복 표현, 기사 서두/결론의 장식적 문장은 제외\n'
        '- summary는 2~4문장으로, 검증에 필요한 사실과 주의점을 중심으로 작성\n'
        '- excerpt는 본문에서 검증 가치가 높은 핵심 문장 1~2개를 그대로 또는 거의 그대로 추출\n'
        '- note에는 본문 추출 제한이나 기사 접근 문제를 짧게 적을 수 있음\n'
        '\n'
        '반드시 아래 키만 가진 JSON 객체를 반환하세요:\n'
        '{\n'
        '  "summary": "...",\n'
        '  "excerpt": "...",\n'
        '  "note": "..."\n'
        '}\n'
    )


def _normalize_news_result(result: NewsEvaluation) -> NewsEvaluation:
    result.score = _clamp(result.score)
    result.grade = _score_to_grade(result.score)
    result.breakdown.currency = _clamp(result.breakdown.currency)
    result.breakdown.relevance = _clamp(result.breakdown.relevance)
    result.breakdown.authority = _clamp(result.breakdown.authority)
    result.breakdown.accuracy = _clamp(result.breakdown.accuracy)
    result.breakdown.purpose = _clamp(result.breakdown.purpose)
    result.flags = [str(flag) for flag in result.flags if str(flag).strip()]
    result.verdict = result.verdict.strip() or _news_verdict(result.score, result.flags)
    result.reason = result.reason.strip()
    return result


def _normalize_patent_result(result: PatentEvaluation) -> PatentEvaluation:
    result.score = _clamp(result.score)
    result.grade = _score_to_grade(result.score)
    result.breakdown.search_match = _clamp(result.breakdown.search_match)
    result.breakdown.legal_status = _clamp(result.breakdown.legal_status)
    result.breakdown.citation_signal = _clamp(result.breakdown.citation_signal)
    result.breakdown.specificity = _clamp(result.breakdown.specificity)
    result.flags = [str(flag) for flag in result.flags if str(flag).strip()]
    result.verdict = result.verdict.strip() or _patent_verdict(result.score, '', result.flags)
    result.reason = result.reason.strip()
    return result


def _normalize_patent_narrative(
    *,
    result: PatentEvidenceNarrative,
    title: str,
    query: str,
    evidence_text: str,
) -> PatentEvidenceNarrative:
    if _is_placeholder_patent_text(result.excerpt):
        result.excerpt = _shorten_text(evidence_text, limit=420) or f'{title}은 {query or "질의 기술"} 관련 핵심 구성/공정을 다루는 특허다.'
    if _is_placeholder_patent_text(result.summary):
        result.summary = (
            f'특허 "{title}"은 {query or "질의 기술"}의 구현 구조와 운전 공정을 제시한다. '
            f'핵심 구성요소와 적용 맥락은 청구항/요약 정보 기준으로 정리되며 추가 원문 검토가 권장된다.'
        )
    if _is_placeholder_patent_text(result.key_point):
        result.key_point = f'{title}은 {query or "질의 기술"} 관련 구현 특허 후보로 분류된다.'

    # 사용자가 원치 않는 "초록 없음" 고정 문구를 note/flags로 반복하지 않도록 정리
    banned_note_markers = (
        '초록이 제공되지',
        '정보가 부족',
        '기술의 구체적인 작동 방식',
    )
    if any(marker in (result.note or '') for marker in banned_note_markers):
        result.note = '원문 기반 세부 보강 필요'
    return result


def _fallback_news_evaluation(
    *,
    title: str,
    provider: str,
    published_at: str,
    query: str,
    description: str,
    support_count: int,
) -> NewsEvaluation:
    currency = _score_currency(published_at)
    relevance = _score_relevance(query, title, description)
    authority = _score_authority(provider)
    accuracy = _score_accuracy(description, support_count)
    purpose = _score_purpose(title, description, provider)

    score = round(
        currency * 0.10
        + relevance * 0.15
        + authority * 0.20
        + accuracy * 0.30
        + purpose * 0.25,
        3,
    )
    flags = _news_flags(currency, relevance, authority, accuracy, purpose, support_count, title, description)
    verdict = _news_verdict(score, flags)
    reason = _news_reason(title, provider, score, currency, relevance, authority, accuracy, purpose, flags)
    return NewsEvaluation(
        score=score,
        grade=_score_to_grade(score),
        breakdown=NewsEvaluationBreakdown(
            currency=currency,
            relevance=relevance,
            authority=authority,
            accuracy=accuracy,
            purpose=purpose,
        ),
        flags=flags,
        verdict=verdict,
        reason=reason,
    )


def _fallback_patent_evaluation(
    *,
    title: str,
    abstract: str,
    query: str,
    status: str,
    citation_count: int,
    application_number: str = '',
) -> PatentEvaluation:
    search_match = _score_patent_search_match(query, title, abstract)
    legal_status = _score_patent_status(status)
    citation_signal = _score_patent_citations(citation_count)
    specificity = _score_patent_specificity(title, abstract, query)

    score = round(
        search_match * 0.35
        + legal_status * 0.25
        + citation_signal * 0.25
        + specificity * 0.15,
        3,
    )
    flags = _patent_flags(search_match, legal_status, citation_signal, specificity, status, citation_count)
    verdict = _patent_verdict(score, status, flags)
    reason = _patent_reason(title, score, search_match, legal_status, citation_signal, specificity, flags)
    return PatentEvaluation(
        score=score,
        grade=_score_to_grade(score),
        breakdown=PatentEvaluationBreakdown(
            search_match=search_match,
            legal_status=legal_status,
            citation_signal=citation_signal,
            specificity=specificity,
        ),
        flags=flags,
        verdict=verdict,
        reason=reason,
    )


def _score_currency(published_at: str) -> float:
    if not published_at:
        return 0.0

    parsed = _parse_date(published_at)
    if parsed is None:
        return 0.2

    days_ago = (date.today() - parsed).days
    if days_ago <= 30:
        return 1.0
    if days_ago <= 180:
        return 0.8
    if days_ago <= 365:
        return 0.6
    if days_ago <= 730:
        return 0.4
    return 0.2


def _score_relevance(query: str, title: str, description: str) -> float:
    query_tokens = set(_tokenize(query))
    if not query_tokens:
        return 0.5

    text_tokens = set(_tokenize(f'{title} {description}'))
    overlap = len(query_tokens & text_tokens)
    ratio = overlap / max(len(query_tokens), 1)

    if ratio >= 0.8:
        return 1.0
    if ratio >= 0.5:
        return 0.85
    if ratio >= 0.3:
        return 0.65
    return 0.35


def _score_authority(provider: str) -> float:
    provider = provider.lower()
    tier1 = (
        'yonhapnews.co.kr',
        'yna.co.kr',
        'chosun.com',
        'joins.com',
        'donga.com',
        'reuters.com',
        'nature.com',
        'science.org',
    )
    tier2 = (
        'dongascience.com',
        'etnews.com',
        'energydaily.co.kr',
        'hankyung.com',
        'mk.co.kr',
        'zdnet.co.kr',
        'sedaily.com',
    )
    tier4 = ('blog', 'tistory.com', 'cafe', 'wordpress.com', 'medium.com')

    if any(domain in provider for domain in tier1):
        return 1.0
    if any(domain in provider for domain in tier2):
        return 0.8
    if any(domain in provider for domain in tier4):
        return 0.2
    return 0.5 if provider else 0.2


def _score_accuracy(description: str, support_count: int) -> float:
    if support_count >= 5:
        return 1.0
    if support_count >= 2:
        score = 0.7
    else:
        score = 0.3

    lowered = description.lower()
    if any(marker in lowered for marker in ('공식 발표', '원문 논문', '공식자료', '논문', '실험 결과')):
        score = min(score + 0.2, 1.0)
    if any(marker in lowered for marker in ('관계자에 따르면', '관계자에', '익명 관계자')):
        score = max(score - 0.2, 0.0)
    if any(marker in lowered for marker in ('보도자료', '자료 제공', '기업 발표', '배포')):
        score = max(score - 0.3, 0.0)
    return round(score, 3)


def _score_purpose(title: str, description: str, provider: str) -> float:
    text = f'{title} {description} {provider}'.lower()
    if any(marker in text for marker in ('광고', '협찬', '후원', '홍보', '기획')):
        return 0.2
    if any(marker in text for marker in ('보도자료', '기업 발표', '자료 제공')):
        return 0.4
    if any(marker in text for marker in ('발표', '밝혔다', '공개', '협약', 'mou')):
        return 0.7
    return 1.0


def _news_flags(
    currency: float,
    relevance: float,
    authority: float,
    accuracy: float,
    purpose: float,
    support_count: int,
    title: str,
    description: str,
) -> list[str]:
    flags: list[str] = []
    if support_count <= 1:
        flags.append('단독 보도')
    if authority <= 0.5:
        flags.append('출처 신뢰도 낮음')
    if accuracy <= 0.4:
        flags.append('교차 확인 불가')
    if purpose <= 0.4:
        flags.append('보도자료/홍보성 가능성')
    if any(marker in f'{title} {description}'.lower() for marker in ('관계자에 따르면', '익명 관계자')):
        flags.append('익명 관계자 의존')
    return flags


def _news_verdict(score: float, flags: list[str]) -> str:
    if score >= 0.75:
        return '신뢰할 수 있는 보도'
    if score >= 0.5:
        if any(flag in flags for flag in ('단독 보도', '보도자료/홍보성 가능성')):
            return '전문 매체 보도이나 교차 확인 필요'
        return '조건부 신뢰, 교차 확인 필요'
    return '단독 근거로 사용 불가'


def _news_reason(
    title: str,
    provider: str,
    score: float,
    currency: float,
    relevance: float,
    authority: float,
    accuracy: float,
    purpose: float,
    flags: list[str],
) -> str:
    return (
        f'출처 {provider} 기사 "{title}"의 종합 점수는 {score:.2f}이며, '
        f'최신성({currency:.2f}), 관련성({relevance:.2f}), 권위성({authority:.2f}), '
        f'정확성({accuracy:.2f}), 목적성({purpose:.2f})을 반영했다. '
        + ('; '.join(flags) if flags else '특이 플래그는 없다.')
    )


def _news_summary(title: str, provider: str, description: str, score: float, flags: list[str], verdict: str) -> str:
    body = description.strip() or '관련 기술 소식을 다룬다.'
    flag_text = f" 주요 주의점은 {', '.join(flags)}다." if flags else ''
    return (
        f'{provider} 기사 "{title}"은 {body} 종합 점수 {score:.2f}로 평가되며, {verdict}.{flag_text}'
    ).strip()


def _shorten_text(text: str, limit: int = 240) -> str:
    cleaned = ' '.join((text or '').split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + '…'


def _is_placeholder_patent_text(text: str) -> bool:
    raw = (text or '').strip()
    if not raw:
        return True
    markers = (
        '초록이 제공되지',
        '정보가 부족',
        '확인할 수 없음',
        '제공되지 않았',
    )
    return any(marker in raw for marker in markers)


def _score_patent_search_match(query: str, title: str, abstract: str) -> float:
    query_tokens = set(_tokenize(query))
    text_tokens = set(_tokenize(f'{title} {abstract}'))
    if not query_tokens:
        return 0.5
    overlap = len(query_tokens & text_tokens)
    ratio = overlap / max(len(query_tokens), 1)
    if ratio >= 0.8:
        return 1.0
    if ratio >= 0.5:
        return 0.85
    if ratio >= 0.3:
        return 0.65
    return 0.35


def _score_patent_status(status: str) -> float:
    status = (status or '').strip()
    if status == '등록':
        return 1.0
    if status == '심사중':
        return 0.7
    return 0.4


def _score_patent_citations(citation_count: int) -> float:
    if citation_count >= 5:
        return 1.0
    if citation_count >= 2:
        return 0.8
    if citation_count >= 1:
        return 0.6
    return 0.2


def _score_patent_specificity(title: str, abstract: str, query: str) -> float:
    text = f'{title} {abstract}'.lower()
    query_tokens = set(_tokenize(query))
    text_tokens = set(_tokenize(text))
    overlap = len(query_tokens & text_tokens)
    if overlap >= 4:
        return 1.0
    if overlap >= 3:
        return 0.85
    if overlap >= 2:
        return 0.65
    return 0.35


def _patent_flags(
    search_match: float,
    legal_status: float,
    citation_signal: float,
    specificity: float,
    status: str,
    citation_count: int,
) -> list[str]:
    flags: list[str] = []
    if search_match < 0.5:
        flags.append('질의어 일치도 낮음')
    if citation_count == 0:
        flags.append('인용문헌 부족')
    if status != '등록':
        flags.append('등록 전 단계')
    if specificity < 0.5:
        flags.append('핵심성 불명확')
    if legal_status < 0.5:
        flags.append('법적 상태 불안정')
    return flags


def _patent_reason(
    title: str,
    score: float,
    search_match: float,
    legal_status: float,
    citation_signal: float,
    specificity: float,
    flags: list[str],
) -> str:
    return (
        f'특허 "{title}"의 핵심성 종합 점수는 {score:.2f}이며, '
        f'질의어 일치도({search_match:.2f}), 법적 상태({legal_status:.2f}), '
        f'인용문헌 신호({citation_signal:.2f}), 기술 구체성({specificity:.2f})을 반영했다. '
        + ('; '.join(flags) if flags else '특이 플래그는 없다.')
    )


def _patent_verdict(score: float, status: str, flags: list[str]) -> str:
    if score >= 0.75 and status == '등록':
        return '핵심기술 가능성 높음'
    if score >= 0.55:
        return '관련기술 또는 핵심기술 후보'
    return '주변기술 가능성 높음'


def _score_to_grade(score: float) -> Literal['HIGH', 'MED', 'LOW']:
    if score >= 0.75:
        return 'HIGH'
    if score >= 0.5:
        return 'MED'
    return 'LOW'


def _parse_date(raw_value: str) -> date | None:
    for fmt in ('%Y-%m-%d', '%Y.%m.%d', '%Y/%m/%d', '%a, %d %b %Y %H:%M:%S %z'):
        try:
            return datetime.strptime(raw_value, fmt).date()
        except ValueError:
            continue
    try:
        dt = datetime.fromisoformat(raw_value)
        return dt.date()
    except ValueError:
        return None


def _clamp(value: Any) -> float:
    try:
        return max(0.0, min(float(value), 1.0))
    except Exception:
        return 0.0


def _tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for raw in (text or '').replace('/', ' ').replace('-', ' ').split():
        cleaned = ''.join(ch for ch in raw if ch.isalnum() or '\uac00' <= ch <= '\ud7a3')
        if cleaned:
            tokens.append(cleaned.lower())
    return tokens
