from __future__ import annotations

import asyncio
from datetime import date
import logging

from openai import AsyncOpenAI

from app.agents.report.pdf_export import export_pdf
from app.core.config import settings
from app.schemas.agent_result import (
    CrossValidatorOutput,
    IndustrialAgentOutput,
    RegulatoryAgentOutput,
    ScientificAgentOutput,
)
from app.schemas.claim import Claim, ClaimJudgement
from app.schemas.report import (
    ChartData,
    CitationMeta,
    ClaimVerdictChart,
    ReportInput,
    ReportOutput,
    RoadmapStep,
    ScoreItem,
    ScoreSummary,
    SectionDraft,
)
from app.schemas.source import SourceItem


logger = logging.getLogger(__name__)

MODEL_NAME = 'gpt-4o-mini'
TEMPERATURE = 0.3
MAX_TOKENS = 4096

_COMMON_SYSTEM_RULES = """당신은 기술 검증 보고서를 작성하는 분석 에이전트다.
- 마크다운 형식으로만 출력한다.
- 최상위 제목(#, ##) 사용을 금지하고 ### 이하만 사용한다.
- 표와 목록을 적극 활용한다.
- 모든 사실 기반 서술은 제공된 입력 데이터와 출처에 근거해야 한다.
- 추측 표현에는 반드시 "(추정)"을 명시한다.
- 출력 언어는 한국어다.
- 각 사실 기반 문장 끝에는 제공된 sources 목록의 실제 숫자 ref_id를 사용해 [^1], [^2] 형식으로 인용 번호를 삽입한다.
- 제공되지 않은 사실을 단정하지 않는다.
"""

_SECTION_TITLES = {
    'section1': '검증 개요',
    'section2': '과학적 근거 분석',
    'section3': '산업화 현황 분석',
    'section4': '규제 및 법률 검토',
    'section5': '최종 평가표 및 해설',
    'section6': '기술도입 로드맵 및 체크리스트',
    'section7': '참고문헌',
}

_TRL_LABELS = {
    1: '기초 이론/실험 단계',
    2: '기술개발 개념 정립 단계',
    3: '실험실 기본성능 검증 단계',
    4: '실험실 핵심성능 평가 단계',
    5: '실험실 시작품 제작 및 성능 평가 단계',
    6: '파일럿 규모 시작품 제작 및 성능 평가 단계',
    7: '신뢰성 평가 및 수요기업 평가 단계',
    8: '시제품 인증 및 표준화 단계',
    9: '양산 및 사업화 단계',
}

_MRL_LABELS = {
    1: '기본 제조 개념 도출 단계',
    2: '제조 개념 및 적용 가능성 정의 단계',
    3: '제조 개념 검증 단계',
    4: '실험실 환경 제조 능력 검증 단계',
    5: '관련 환경 생산 능력 검증 단계',
    6: '시제품 제작 및 생산 단계',
    7: '시험 인증 단계 (LRIP)',
    8: '본격 생산 준비 단계',
    9: '본격 생산 단계',
    10: '양산 단계',
}

_CRI_LABELS = {
    1: '가상적 상업화 제안 단계',
    2: '소규모 상업 시험 단계',
    3: '상업적 규모 확대 단계',
    4: '다수 상업적 적용 단계',
    5: '시장 경쟁 단계',
    6: '은행 자산 등급 단계 (완전 성숙)',
}

_CONFIDENCE_SCORES = {
    'HIGH': 0.9,
    'MED': 0.6,
    'LOW': 0.3,
}


def _get_client() -> AsyncOpenAI | None:
    if not settings.OPENAI_API_KEY:
        return None
    return AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


def _claim_label(claim: Claim) -> str:
    return claim.claim_text or claim.claim or '주장 정보 없음'


def _tech_label(claims: list[Claim]) -> str:
    if not claims:
        return '기술'
    first = claims[0]
    return first.technology or first.claim_text or first.claim or '기술'


def _safe_join(items: list[str]) -> str:
    return ', '.join([item for item in items if item]) if items else ''


def _safe_getattr(obj: object, field_name: str, default=None):
    try:
        return getattr(obj, field_name, default)
    except Exception:
        return default


def _clip_prompt_text(value: str | None, max_chars: int | None = None) -> str | None:
    text = (value or '').strip()
    if not text:
        return None
    if max_chars is not None and len(text) > max_chars:
        return text[:max_chars] + '...(이하 생략)'
    return text


def _append_prompt_line(lines: list[str], label: str, value: str | None, max_chars: int | None = None) -> None:
    text = _clip_prompt_text(value, max_chars)
    if text:
        lines.append(f'{label}: {text}')


def _format_prompt_list(values: object, max_chars: int | None = None) -> str | None:
    if isinstance(values, list):
        joined = ', '.join([str(item).strip() for item in values if str(item).strip()])
        return _clip_prompt_text(joined, max_chars)
    return _clip_prompt_text(str(values) if values is not None else '', max_chars)


def _match_source_raw_text(item: object, sources: list[SourceItem], max_chars: int | None = None) -> str | None:
    item_title = (_safe_getattr(item, 'title', '') or '').strip()
    item_url = (_safe_getattr(item, 'url', '') or _safe_getattr(item, 'primary_url', '') or '').strip()
    for source in sources:
        source_title = (source.title or '').strip()
        source_url = (source.url or '').strip()
        if (item_title and source_title and item_title == source_title) or (item_url and source_url and item_url == source_url):
            return _clip_prompt_text(source.raw_text, max_chars)
    return None


def _build_scientific_evidence_block(
    papers: list[object],
    sources: list[SourceItem],
    max_chars: int | None = None,
) -> str:
    lines: list[str] = []
    for index, paper in enumerate(papers[:3], start=1):
        title = _safe_getattr(paper, 'title', '제목 미상')
        year = _safe_getattr(paper, 'year', None)
        header = f'[논문 {index}] 제목: {title}'
        if year:
            header += f' ({year})'
        lines.append(header)
        _append_prompt_line(lines, '요약', _safe_getattr(paper, 'summary', None), max_chars)
        _append_prompt_line(lines, '핵심 포인트', _safe_getattr(paper, 'key_point', None), max_chars)
        _append_prompt_line(lines, '발췌', _safe_getattr(paper, 'excerpt', None), max_chars)
        _append_prompt_line(
            lines,
            '한계',
            _format_prompt_list(_safe_getattr(paper, 'limitations', None), max_chars),
            max_chars,
        )
        _append_prompt_line(
            lines,
            '조건',
            _format_prompt_list(_safe_getattr(paper, 'conditions', None), max_chars),
            max_chars,
        )
        _append_prompt_line(lines, '원문 스니펫', _match_source_raw_text(paper, sources, max_chars), max_chars)
        lines.append('')
    return '\n'.join(lines).strip() or '- 논문 근거 텍스트 없음'


def _build_industrial_news_block(news_items: list[object], max_chars: int | None = None) -> str:
    lines: list[str] = []
    for index, news in enumerate(news_items[:3], start=1):
        title = _safe_getattr(news, 'title', '제목 미상')
        published_at = _safe_getattr(news, 'published_at', None)
        header = f'[뉴스 {index}] 제목: {title}'
        if published_at:
            header += f' ({published_at})'
        lines.append(header)
        _append_prompt_line(lines, '요약', _safe_getattr(news, 'summary', None), max_chars)
        _append_prompt_line(lines, '발췌', _safe_getattr(news, 'excerpt', None), max_chars)
        _append_prompt_line(lines, '선정 이유', _safe_getattr(news, 'reason', None), max_chars)
        lines.append('')
    return '\n'.join(lines).strip() or '- 뉴스 근거 텍스트 없음'


def _build_industrial_patent_block(patents: list[object], max_chars: int | None = None) -> str:
    lines: list[str] = []
    for index, patent in enumerate(patents[:3], start=1):
        title = _safe_getattr(patent, 'title', '제목 미상')
        lines.append(f'[특허 {index}] 제목: {title}')
        _append_prompt_line(lines, '요약', _safe_getattr(patent, 'summary', None), max_chars)
        _append_prompt_line(lines, '핵심 포인트', _safe_getattr(patent, 'key_point', None), max_chars)
        _append_prompt_line(lines, '발췌', _safe_getattr(patent, 'excerpt', None), max_chars)
        _append_prompt_line(
            lines,
            '플래그',
            _format_prompt_list(_safe_getattr(patent, 'flags', None), max_chars),
            max_chars,
        )
        lines.append('')
    return '\n'.join(lines).strip() or '- 특허 근거 텍스트 없음'


def _build_regulatory_evidence_block(evidences: list[object], max_chars: int | None = None) -> str:
    lines: list[str] = []
    for index, evidence in enumerate(evidences[:3], start=1):
        title = _safe_getattr(evidence, 'title', '제목 미상')
        lines.append(f'[규제 근거 {index}] {title}')
        _append_prompt_line(lines, '요약', _safe_getattr(evidence, 'summary', None), max_chars)
        _append_prompt_line(lines, '발췌', _safe_getattr(evidence, 'excerpt', None), max_chars)
        _append_prompt_line(lines, '적용 이유', _safe_getattr(evidence, 'reason', None), max_chars)
        lines.append('')
    return '\n'.join(lines).strip() or '- 규제 근거 텍스트 없음'


def _extract_first_int(value: str | None) -> int | None:
    if not value:
        return None
    digits = [token for token in ''.join(ch if ch.isdigit() else ' ' for ch in value).split() if token.isdigit()]
    if not digits:
        return None
    try:
        return int(digits[0])
    except ValueError:
        return None


def _build_apa_citation(source: SourceItem) -> str:
    if source.apa7_citation:
        return source.apa7_citation

    year = str(source.year) if source.year is not None else 'n.d.'
    title = source.title or '제목 미상'
    publisher = source.publisher or '발행처 미상'
    url = source.url or ''

    if source.authors:
        author_text = _safe_join(source.authors)
        citation = f'{author_text}. ({year}). {title}. {publisher}.'
    else:
        citation = f'{title}. ({year}). {publisher}.'

    return f'{citation} {url}'.strip()


def _normalize_sources(report_input: ReportInput) -> list[SourceItem]:
    normalized: list[SourceItem] = []
    seen: set[str] = set()

    for result in [
        report_input.scientific,
        report_input.industrial,
        report_input.regulatory,
        report_input.cross_validation,
    ]:
        for source in getattr(result, 'sources', []):
            key = f'{source.title}|{source.url}|{source.raw_text}'
            if key in seen:
                continue
            seen.add(key)
            normalized.append(source)

    assigned: list[SourceItem] = []
    for index, source in enumerate(normalized, start=1):
        assigned.append(
            source.model_copy(
                update={
                    'ref_id': index,
                    'apa7_citation': _build_apa_citation(source),
                }
            )
        )
    return assigned


def _sources_for_refs(all_sources: list[SourceItem], selected_sources: list[SourceItem]) -> list[SourceItem]:
    selected_keys = {f'{source.title}|{source.url}|{source.raw_text}' for source in selected_sources}
    return [
        source
        for source in all_sources
        if f'{source.title}|{source.url}|{source.raw_text}' in selected_keys
    ]


def _build_source_index_block(sources: list[SourceItem]) -> str:
    if not sources:
        return '- 제공된 출처 없음'
    return '\n'.join([f'- [{source.ref_id}: {source.title or "제목 미상"}]' for source in sources])


def _format_source_line(source: SourceItem) -> str:
    title = source.title or '제목 미상'
    authors = _safe_join(source.authors) or '저자 미상'
    year = str(source.year) if source.year is not None else '연도 미상'
    publisher = source.publisher or '발행처 미상'
    url = source.url or 'URL 없음'
    snippet = source.raw_text or '스니펫 없음'
    return (
        f"- ref_id={source.ref_id or '미지정'} | 유형={source.source_type} | 제목={title} | "
        f"저자={authors} | 연도={year} | 발행처={publisher} | URL={url} | 스니펫={snippet}"
    )


def _format_sources_block(sources: list[SourceItem]) -> str:
    if not sources:
        return '- 출처 없음'
    return '\n'.join(_format_source_line(source) for source in sources)


def _build_claims_table(claims: list[Claim]) -> str:
    rows = ['| claim_id | 주장 | 카테고리 |', '| --- | --- | --- |']
    for claim in claims:
        rows.append(
            f"| {claim.claim_id or '-'} | {_claim_label(claim)} | {claim.category or '-'} |"
        )
    return '\n'.join(rows)


def _build_metric_table(report_input: ReportInput) -> str:
    scientific = report_input.scientific
    industrial = report_input.industrial
    regulatory = report_input.regulatory
    rows = [
        '| 지표 | 현재 수준 | 범위 | 판단 근거 요약 |',
        '| --- | --- | --- | --- |',
        f"| TRL | {scientific.trl_estimate or '-'} | 1~9 | {scientific.trl_rationale or scientific.summary or '-'} |",
        f"| MRL | {industrial.mrl_estimate or '-'} | 1~10 | {industrial.mrl_rationale or industrial.summary or '-'} |",
        f"| CRI | {regulatory.cri_estimate or '-'} | 1~6 | {regulatory.cri_rationale or regulatory.summary or '-'} |",
    ]
    return '\n'.join(rows)


def _build_claim_judgement_table(judgements: list[ClaimJudgement], claims: list[Claim]) -> str:
    claim_map = {claim.claim_id: claim for claim in claims}
    rows = ['| 주장 | 판정 | 종합 신뢰도 | 근거 요약 |', '| --- | --- | --- | --- |']
    for judgement in judgements:
        claim = claim_map.get(judgement.claim_id)
        claim_text = _claim_label(claim) if claim is not None else judgement.claim_id or '주장 정보 없음'
        rows.append(
            f"| {claim_text} | {judgement.judgement or '-'} | "
            f"{judgement.overall_confidence or '-'} | {judgement.rationale_summary or '-'} |"
        )
    return '\n'.join(rows)


def _fallback_section(section_id: str, error_message: str) -> SectionDraft:
    title = _SECTION_TITLES[section_id]
    return SectionDraft(
        section_id=section_id,
        title=title,
        markdown=f'### {title}\n\n*해당 섹션 생성 중 오류가 발생했습니다.*',
        has_error=True,
        error=error_message,
    )


async def _call_llm(section_title: str, system_prompt: str, user_prompt: str) -> str:
    client = _get_client()
    if client is None:
        raise RuntimeError('OPENAI_API_KEY is not configured')

    response = await client.responses.create(
        model=MODEL_NAME,
        temperature=TEMPERATURE,
        max_output_tokens=MAX_TOKENS,
        input=[
            {'role': 'system', 'content': [{'type': 'input_text', 'text': system_prompt}]},
            {'role': 'user', 'content': [{'type': 'input_text', 'text': user_prompt}]},
        ],
    )
    content = (response.output_text or '').strip()
    if not content:
        raise RuntimeError(f'{section_title} LLM output was empty')
    return content


async def _generate_section(
    section_id: str,
    system_context: str,
    user_prompt: str,
    ref_ids: list[int],
) -> SectionDraft:
    title = _SECTION_TITLES[section_id]
    try:
        markdown = await _call_llm(title, system_context, user_prompt)
        return SectionDraft(
            section_id=section_id,
            title=title,
            markdown=markdown,
            ref_ids=ref_ids,
            has_error=False,
            error=None,
        )
    except Exception as exc:
        logger.exception('Failed to generate section %s', section_id)
        return _fallback_section(section_id, str(exc))


def _section_sources_ref_ids(sources: list[SourceItem]) -> list[int]:
    return [source.ref_id for source in sources if source.ref_id]


def _build_section_system_prompt(base_context: str, sources: list[SourceItem]) -> str:
    return (
        f"{_COMMON_SYSTEM_RULES}\n"
        f"{base_context}\n"
        "해당 섹션에서 사용할 수 있는 sources 목록:\n"
        f"{_build_source_index_block(sources)}"
    )


def _prompt_builder_fallback(
    section_id: str,
    sources: list[SourceItem],
    exc: Exception,
) -> tuple[str, str, list[int]]:
    logger.exception('Failed to build prompts for section %s', section_id)
    system_prompt = _build_section_system_prompt(f'{_SECTION_TITLES[section_id]} 섹션 작성', sources)
    user_prompt = (
        f"섹션 제목은 '### {_SECTION_TITLES[section_id]}'로 시작하세요.\n"
        "해당 섹션 데이터를 불러오는 중 오류가 발생했습니다.\n"
        f"오류 요약: {exc}"
    )
    return system_prompt, user_prompt, _section_sources_ref_ids(sources)


def _build_section1_prompts(
    report_input: ReportInput,
    company_context: str,
    all_sources: list[SourceItem],
) -> tuple[str, str, list[int]]:
    try:
        claims_table = _build_claims_table(report_input.claims)
        system_prompt = _build_section_system_prompt(
            f"회사 일반 현황 컨텍스트:\n{company_context or '제공된 회사 컨텍스트 없음'}",
            all_sources,
        )
        user_prompt = f"""섹션 제목은 '### 검증 개요'로 시작하세요.
회사명: {report_input.company_name}
검증 대상 기술: {_tech_label(report_input.claims)}

검증 대상 주장 목록 표:
{claims_table}

사용 가능한 출처 상세:
{_format_sources_block(all_sources)}

작성 요구:
- 회사 소개와 본 검증의 목적을 짧게 정리한다.
- 검증 대상 주장 목록을 표를 활용해 설명한다.
- 회사 일반 현황 컨텍스트가 없으면 그 한계를 드러내되 보고서 톤은 유지한다.
"""
        return system_prompt, user_prompt, _section_sources_ref_ids(all_sources)
    except Exception as exc:
        return _prompt_builder_fallback('section1', all_sources, exc)


def _build_section2_prompts(
    report_input: ReportInput,
    section_sources: list[SourceItem],
) -> tuple[str, str, list[int]]:
    try:
        scientific = report_input.scientific
        system_prompt = _build_section_system_prompt('과학적 근거 분석 섹션 작성', section_sources)
        paper_list = chr(10).join(
            [
                f"- {(_safe_getattr(paper, 'title', '제목 미상'))} ({_safe_getattr(paper, 'year', '-')}) / "
                f"{_safe_getattr(paper, 'journal', '-') or '-'} / grade={_safe_getattr(paper, 'grade_level', '-') or '-'}"
                for paper in (_safe_getattr(scientific, 'papers', []) or [])
            ]
        ) or '- 논문 정보 없음'
        evidence_block = _build_scientific_evidence_block(_safe_getattr(scientific, 'papers', []) or [], section_sources)
        user_prompt = f"""섹션 제목은 '### 과학적 근거 분석'으로 시작하세요.
Scientific 요약: {scientific.summary or '-'}
TRL 추정값: {scientific.trl_estimate or '-'}
TRL 판단 근거: {scientific.trl_rationale or '-'}
과학 신뢰도 판정: {report_input.cross_validation.scientific_confidence or '-'}

논문 목록:
{paper_list}

논문 근거 텍스트:
{evidence_block}

출처:
{_format_sources_block(section_sources)}

작성 요구:
- 과학적 근거 수준을 요약한다.
- TRL 현재 추정 수준과 그 판단 근거를 분리해 설명한다.
- cross validation의 과학 신뢰도 판정을 함께 서술한다.
"""
        if len(user_prompt) > 50000:
            evidence_block = _build_scientific_evidence_block(
                _safe_getattr(scientific, 'papers', []) or [],
                section_sources,
                max_chars=500,
            )
            user_prompt = f"""섹션 제목은 '### 과학적 근거 분석'으로 시작하세요.
Scientific 요약: {scientific.summary or '-'}
TRL 추정값: {scientific.trl_estimate or '-'}
TRL 판단 근거: {scientific.trl_rationale or '-'}
과학 신뢰도 판정: {report_input.cross_validation.scientific_confidence or '-'}

논문 목록:
{paper_list}

논문 근거 텍스트:
{evidence_block}

출처:
{_format_sources_block(section_sources)}

작성 요구:
- 과학적 근거 수준을 요약한다.
- TRL 현재 추정 수준과 그 판단 근거를 분리해 설명한다.
- cross validation의 과학 신뢰도 판정을 함께 서술한다.
"""
        return system_prompt, user_prompt, _section_sources_ref_ids(section_sources)
    except Exception as exc:
        return _prompt_builder_fallback('section2', section_sources, exc)


def _build_section3_prompts(
    report_input: ReportInput,
    section_sources: list[SourceItem],
) -> tuple[str, str, list[int]]:
    try:
        industrial = report_input.industrial
        system_prompt = _build_section_system_prompt('산업화 현황 분석 섹션 작성', section_sources)
        news_items = _safe_getattr(industrial, 'news', []) or []
        patent_items = _safe_getattr(industrial, 'patents', []) or []
        news_list = chr(10).join(
            [
                f"- {(_safe_getattr(news, 'title', '제목 미상'))} / "
                f"{(_safe_getattr(news, 'publisher', '-') or '-')} / "
                f"{(_safe_getattr(news, 'published_at', '-') or '-')} / "
                f"level={(_safe_getattr(news, 'craap_level', '-') or '-')}"
                for news in news_items
            ]
        ) or '- 뉴스 정보 없음'
        patent_list = chr(10).join(
            [
                f"- {(_safe_getattr(patent, 'title', '제목 미상'))} / "
                f"{(_safe_getattr(patent, 'applicant', '-') or '-')} / "
                f"{(_safe_getattr(patent, 'application_date', '-') or '-')} / "
                f"상태={(_safe_getattr(patent, 'status', '-') or '-')}"
                for patent in patent_items
            ]
        ) or '- 특허 정보 없음'
        news_evidence = _build_industrial_news_block(news_items)
        patent_evidence = _build_industrial_patent_block(patent_items)
        user_prompt = f"""섹션 제목은 '### 산업화 현황 분석'으로 시작하세요.
Industrial 요약: {industrial.summary or '-'}
MRL 추정값: {industrial.mrl_estimate or '-'}
MRL 판단 근거: {industrial.mrl_rationale or '-'}
산업 신뢰도 판정: {report_input.cross_validation.industrial_confidence or '-'}

뉴스 목록:
{news_list}

뉴스 근거 텍스트:
{news_evidence}

특허 목록:
{patent_list}

특허 근거 텍스트:
{patent_evidence}

출처:
{_format_sources_block(section_sources)}

작성 요구:
- 산업화 및 상용화 시그널을 요약한다.
- MRL 현재 추정 수준과 그 판단 근거를 설명한다.
- cross validation의 산업 신뢰도 판정을 반영한다.
"""
        if len(user_prompt) > 50000:
            news_evidence = _build_industrial_news_block(news_items, max_chars=500)
            patent_evidence = _build_industrial_patent_block(patent_items, max_chars=500)
            user_prompt = f"""섹션 제목은 '### 산업화 현황 분석'으로 시작하세요.
Industrial 요약: {industrial.summary or '-'}
MRL 추정값: {industrial.mrl_estimate or '-'}
MRL 판단 근거: {industrial.mrl_rationale or '-'}
산업 신뢰도 판정: {report_input.cross_validation.industrial_confidence or '-'}

뉴스 목록:
{news_list}

뉴스 근거 텍스트:
{news_evidence}

특허 목록:
{patent_list}

특허 근거 텍스트:
{patent_evidence}

출처:
{_format_sources_block(section_sources)}

작성 요구:
- 산업화 및 상용화 시그널을 요약한다.
- MRL 현재 추정 수준과 그 판단 근거를 설명한다.
- cross validation의 산업 신뢰도 판정을 반영한다.
"""
        return system_prompt, user_prompt, _section_sources_ref_ids(section_sources)
    except Exception as exc:
        return _prompt_builder_fallback('section3', section_sources, exc)


def _build_section4_prompts(
    report_input: ReportInput,
    section_sources: list[SourceItem],
) -> tuple[str, str, list[int]]:
    try:
        regulatory = report_input.regulatory
        system_prompt = _build_section_system_prompt('규제 및 법률 검토 섹션 작성', section_sources)
        regulatory_evidences = _safe_getattr(regulatory, 'evidences', []) or []
        evidence_block = _build_regulatory_evidence_block(regulatory_evidences)
        user_prompt = f"""섹션 제목은 '### 규제 및 법률 검토'로 시작하세요.
Regulatory 요약: {regulatory.summary or '-'}
규제 판정: {regulatory.verdict or '-'}
CRI 추정값: {regulatory.cri_estimate or '-'}
CRI 판단 근거: {regulatory.cri_rationale or '-'}
규제 신뢰도 판정: {report_input.cross_validation.regulatory_confidence or '-'}
적용 가능 규정: {_safe_join(regulatory.applicable_regulations) or '-'}
인센티브: {_safe_join(regulatory.incentives) or '-'}
리스크: {_safe_join(regulatory.risks) or '-'}
규제 근거 요약: {_safe_getattr(regulatory, 'evidence_summary', '') or '-'}
판단 이유: {_safe_getattr(regulatory, 'reason', '') or '-'}
파이프라인 메모: {_safe_join(_safe_getattr(regulatory, 'pipeline_notes', []) or []) or '-'}

규제 근거 텍스트:
{evidence_block}

출처:
{_format_sources_block(section_sources)}

작성 요구:
- 규제 적용성, 인센티브, 리스크를 구조적으로 정리한다.
- CRI 현재 추정 수준과 그 판단 근거를 설명한다.
- cross validation의 규제 신뢰도 판정을 반영한다.
"""
        if len(user_prompt) > 50000:
            evidence_block = _build_regulatory_evidence_block(regulatory_evidences, max_chars=500)
            user_prompt = f"""섹션 제목은 '### 규제 및 법률 검토'로 시작하세요.
Regulatory 요약: {regulatory.summary or '-'}
규제 판정: {regulatory.verdict or '-'}
CRI 추정값: {regulatory.cri_estimate or '-'}
CRI 판단 근거: {regulatory.cri_rationale or '-'}
규제 신뢰도 판정: {report_input.cross_validation.regulatory_confidence or '-'}
적용 가능 규정: {_safe_join(regulatory.applicable_regulations) or '-'}
인센티브: {_safe_join(regulatory.incentives) or '-'}
리스크: {_safe_join(regulatory.risks) or '-'}
규제 근거 요약: {_safe_getattr(regulatory, 'evidence_summary', '') or '-'}
판단 이유: {_safe_getattr(regulatory, 'reason', '') or '-'}
파이프라인 메모: {_safe_join(_safe_getattr(regulatory, 'pipeline_notes', []) or []) or '-'}

규제 근거 텍스트:
{evidence_block}

출처:
{_format_sources_block(section_sources)}

작성 요구:
- 규제 적용성, 인센티브, 리스크를 구조적으로 정리한다.
- CRI 현재 추정 수준과 그 판단 근거를 설명한다.
- cross validation의 규제 신뢰도 판정을 반영한다.
"""
        return system_prompt, user_prompt, _section_sources_ref_ids(section_sources)
    except Exception as exc:
        return _prompt_builder_fallback('section4', section_sources, exc)


def _build_section5_prompts(
    report_input: ReportInput,
    section2: SectionDraft,
    section3: SectionDraft,
    section4: SectionDraft,
    all_sources: list[SourceItem],
) -> tuple[str, str, list[int]]:
    try:
        system_prompt = _build_section_system_prompt('최종 평가표 및 해설 섹션 작성', all_sources)
        metric_table = _build_metric_table(report_input)
        judgement_table = _build_claim_judgement_table(report_input.cross_validation.results, report_input.claims)
        user_prompt = f"""섹션 제목은 '### 최종 평가표 및 해설'로 시작하세요.
이전 섹션 초안 참고:

[section2]
{section2.markdown}

[section3]
{section3.markdown}

[section4]
{section4.markdown}

반드시 아래 표를 포함하세요.
지표 평가표:
{metric_table}

주장별 판정 표:
{judgement_table}

종합 판정: {report_input.cross_validation.overall_verdict or '-'}
종합 신뢰도: {report_input.cross_validation.overall_confidence or '-'}
상충 정보: {_safe_join(report_input.cross_validation.conflicts) or '-'}

출처:
{_format_sources_block(all_sources)}

작성 요구:
- 위 두 표를 포함한다.
- 표 아래에 각 지표별 해설을 서술한다.
- 주장별 판정 결과를 종합해 기술도입 가능성을 평가한다.
"""
        return system_prompt, user_prompt, _section_sources_ref_ids(all_sources)
    except Exception as exc:
        return _prompt_builder_fallback('section5', all_sources, exc)


def _build_section6_prompts(
    report_input: ReportInput,
    section5: SectionDraft,
    company_context_section6: str,
    all_sources: list[SourceItem],
) -> tuple[str, str, list[int]]:
    try:
        system_prompt = _build_section_system_prompt(
            f"기술도입 로드맵용 회사 컨텍스트:\n{company_context_section6 or '제공된 section6 전용 컨텍스트 없음'}",
            all_sources,
        )
        user_prompt = f"""섹션 제목은 '### 기술도입 로드맵 및 체크리스트'로 시작하세요.
회사명: {report_input.company_name}
검증 대상 기술: {_tech_label(report_input.claims)}

이전 섹션 초안:
{section5.markdown}

TRL: {report_input.scientific.trl_estimate or '-'}
MRL: {report_input.industrial.mrl_estimate or '-'}
CRI: {report_input.regulatory.cri_estimate or '-'}

출처:
{_format_sources_block(all_sources)}

작성 요구:
- SK이노베이션의 기술도입 로드맵을 4단계 이상 phase 기반으로 작성한다.
- 각 phase는 반드시 아래 구조를 따른다:
  - 단계명
  - 목표
  - TRL/MRL/CRI 목표 범위
  - 핵심 과업
  - 필요 자원/인프라
  - 주요 리스크 및 게이트 조건
- 로드맵은 단일 표 하나로 끝내지 말고 단계형 보고서 서술로 구성한다.
- 체크리스트는 단일 '- [ ]' 나열 대신 아래 3개 범주로 나누어 표 형태로 작성한다:
  - 기술 검증 체크리스트
  - 생산/공급망 체크리스트
  - 규제/사업화 체크리스트
- 체크리스트 표는 '항목 | 중요도 | 관련 지표 | 비고' 컬럼을 사용한다.
- 컨텍스트가 불충분한 부분은 "(추정)"을 표시한다.
"""
        return system_prompt, user_prompt, _section_sources_ref_ids(all_sources)
    except Exception as exc:
        return _prompt_builder_fallback('section6', all_sources, exc)


def _build_section7(all_sources: list[SourceItem]) -> SectionDraft:
    lines = ['### 참고문헌', '']
    if not all_sources:
        lines.append('- 참고문헌 정보가 제공되지 않았습니다.')
    else:
        for source in all_sources:
            lines.append(f'- [^{source.ref_id}] {source.apa7_citation}')

    return SectionDraft(
        section_id='section7',
        title=_SECTION_TITLES['section7'],
        markdown='\n'.join(lines),
        ref_ids=_section_sources_ref_ids(all_sources),
        has_error=False,
        error=None,
    )


def _build_toc(section_drafts: list[SectionDraft]) -> str:
    return '\n'.join([f"- {draft.title}" for draft in section_drafts])


def _merge_markdown(report_input: ReportInput, section_drafts: list[SectionDraft]) -> str:
    tech_name = _tech_label(report_input.claims)
    body = '\n\n'.join([draft.markdown for draft in section_drafts])
    return (
        f"# {tech_name} 기술 검증 보고서\n\n"
        f"작성일: {date.today().isoformat()}\n\n"
        f"## 목차\n{_build_toc(section_drafts)}\n\n"
        f"{body}\n\n---\n"
        "*본 보고서는 AI 기반 분석 도구를 활용하여 생성되었습니다.\n"
        "최종 의사결정 전 전문가 검토를 권장합니다.*"
    )


def _build_citation_metadata(all_sources: list[SourceItem]) -> list[CitationMeta]:
    return [
        CitationMeta(
            ref_id=source.ref_id,
            apa7_citation=source.apa7_citation or '',
            raw_text=source.raw_text,
            url=source.url,
            source_type=source.source_type,
        )
        for source in all_sources
    ]


def _build_score_item(
    value_text: str | None,
    rationale: str,
    min_value: int,
    max_value: int,
    labels: dict[int, str],
) -> ScoreItem:
    value = _extract_first_int(value_text)
    return ScoreItem(
        value=value,
        min=min_value,
        max=max_value,
        label=labels.get(value, '평가 불가'),
        rationale=(rationale or '').strip(),
    )


def _build_score_summary(report_input: ReportInput) -> ScoreSummary:
    scientific = report_input.scientific
    industrial = report_input.industrial
    regulatory = report_input.regulatory
    return ScoreSummary(
        trl=_build_score_item(
            scientific.trl_estimate,
            scientific.trl_rationale or scientific.summary,
            1,
            9,
            _TRL_LABELS,
        ),
        mrl=_build_score_item(
            industrial.mrl_estimate,
            industrial.mrl_rationale or industrial.summary,
            1,
            10,
            _MRL_LABELS,
        ),
        cri=_build_score_item(
            regulatory.cri_estimate,
            regulatory.cri_rationale or regulatory.summary,
            1,
            6,
            _CRI_LABELS,
        ),
    )


def _confidence_to_float(value: str | None) -> float | None:
    if value is None:
        return None
    return _CONFIDENCE_SCORES.get(value.upper())


def _build_claim_verdicts(report_input: ReportInput) -> list[ClaimVerdictChart]:
    claim_map = {claim.claim_id: claim for claim in report_input.claims}
    charts: list[ClaimVerdictChart] = []
    for judgement in report_input.cross_validation.results:
        claim = claim_map.get(judgement.claim_id)
        charts.append(
            ClaimVerdictChart(
                claim_id=judgement.claim_id or '',
                claim_text=_claim_label(claim) if claim else (judgement.claim_id or '주장 정보 없음'),
                verdict=judgement.judgement,
                confidence=_confidence_to_float(judgement.overall_confidence) or 0.0,
                scientific_confidence=_confidence_to_float(judgement.scientific_confidence),
                industrial_confidence=_confidence_to_float(judgement.industrial_confidence),
                regulatory_confidence=_confidence_to_float(judgement.regulatory_confidence),
            )
        )
    return charts


def _build_chart_data(report_input: ReportInput) -> ChartData:
    # TODO: section6 완성 후 로드맵 파싱 또는 LLM 구조화 추출 연결
    return ChartData(
        score_summary=_build_score_summary(report_input),
        claim_verdicts=_build_claim_verdicts(report_input),
        roadmap_steps=[],
    )


async def generate_report(
    report_input: ReportInput,
    company_context: str = '',
    company_context_section6: str = '',
) -> ReportOutput:
    try:
        all_sources = _normalize_sources(report_input)
        chart_data = _build_chart_data(report_input)
        scientific_sources = _sources_for_refs(all_sources, report_input.scientific.sources)
        industrial_sources = _sources_for_refs(all_sources, report_input.industrial.sources)
        regulatory_sources = _sources_for_refs(all_sources, report_input.regulatory.sources)

        section1_prompts = _build_section1_prompts(report_input, company_context, all_sources)
        section2_prompts = _build_section2_prompts(report_input, scientific_sources)
        section3_prompts = _build_section3_prompts(report_input, industrial_sources)
        section4_prompts = _build_section4_prompts(report_input, regulatory_sources)

        section1_task = _generate_section(
            'section1',
            *section1_prompts,
        )
        section2_task = _generate_section(
            'section2',
            *section2_prompts,
        )
        section3_task = _generate_section(
            'section3',
            *section3_prompts,
        )
        section4_task = _generate_section(
            'section4',
            *section4_prompts,
        )

        section1, section2, section3, section4 = await asyncio.gather(
            section1_task,
            section2_task,
            section3_task,
            section4_task,
        )

        section5 = await _generate_section(
            'section5',
            *_build_section5_prompts(report_input, section2, section3, section4, all_sources),
        )
        section6 = await _generate_section(
            'section6',
            *_build_section6_prompts(report_input, section5, company_context_section6, all_sources),
        )
        section7 = _build_section7(all_sources)

        section_drafts = [section1, section2, section3, section4, section5, section6, section7]
        merged_markdown = _merge_markdown(report_input, section_drafts)
        report_title = f'{_tech_label(report_input.claims)} 기술 검증 보고서'
        pdf_path = export_pdf(merged_markdown, chart_data=chart_data, title=report_title)

        return ReportOutput(
            markdown=merged_markdown,
            report_markdown=merged_markdown,
            section_drafts=section_drafts,
            citation_metadata=_build_citation_metadata(all_sources),
            chart_data=chart_data,
            pdf_path=pdf_path,
            error=None,
        )
    except Exception as exc:
        logger.exception('Failed to generate full report output')
        return ReportOutput(
            markdown='',
            report_markdown='',
            section_drafts=[],
            citation_metadata=[],
            chart_data=None,
            pdf_path=None,
            error=str(exc),
        )


def _scientific_sources_md(scientific: ScientificAgentOutput) -> str:
    lines: list[str] = [
        "### 3.1 논문·식별자 (Scientific)",
        "",
    ]
    if scientific.error:
        lines.append(f"- _Scientific 단계 오류:_ {scientific.error}")
        lines.append("")
        return "\n".join(lines)
    if not scientific.papers:
        lines.append("- 상위 논문이 없거나 검색 결과가 비어 있습니다.")
        lines.append("")
        return "\n".join(lines)
    for i, p in enumerate(scientific.papers[:15], 1):
        head = f"{i}. **{p.title}**"
        if p.year:
            head += f" ({p.year})"
        lines.append(f"- {head}")
        if p.journal:
            lines.append(f"  - 저널·출처: {p.journal}")
        meta: list[str] = []
        if p.url:
            meta.append(f"[링크]({p.url})")
        if p.doi:
            meta.append(f"DOI: `{p.doi}`")
        if p.arxiv_id:
            meta.append(f"arXiv: `{p.arxiv_id}`")
        if p.openalex_id:
            meta.append(f"OpenAlex: `{p.openalex_id}`")
        if p.semantic_scholar_id:
            meta.append(f"Semantic Scholar: `{p.semantic_scholar_id}`")
        if meta:
            lines.append("  - " + " · ".join(meta))
        lines.append("")
    return "\n".join(lines)


def _industrial_sources_md(industrial: IndustrialAgentOutput) -> str:
    lines: list[str] = [
        "### 3.2 산업·뉴스 (Industrial)",
        "",
    ]
    if industrial.error:
        lines.append(f"- _Industrial 단계 오류:_ {industrial.error}")
        lines.append("")
        return "\n".join(lines)
    if not industrial.news:
        lines.append("- 뉴스 항목이 없습니다.")
        lines.append("")
        return "\n".join(lines)
    for n in industrial.news[:12]:
        line = f"- **{n.title}**"
        if n.publisher:
            line += f" — {n.publisher}"
        lines.append(line)
        if n.published_at:
            lines.append(f"  - 일자: {n.published_at}")
        if n.url:
            lines.append(f"  - [링크]({n.url})")
        lines.append("")
    return "\n".join(lines)


def _sources_section_md(
    scientific: ScientificAgentOutput,
    industrial: IndustrialAgentOutput,
) -> str:
    return "\n".join(
        [
            "## 3. 근거·출처 (자동 수집)",
            "",
            _scientific_sources_md(scientific),
            _industrial_sources_md(industrial),
        ]
    )


def _regulatory_section_md(regulatory: RegulatoryAgentOutput) -> str:
    lines = [
        "## 5. 규제·정책 환경 (요약)",
        "",
        f"- 적용성 판정: **{regulatory.verdict}** (신뢰도 지표: {regulatory.confidence} — 규제 ‘출처 신뢰’가 아닌 **해석 불확실성** 표시)",
        "",
    ]
    if regulatory.applicable_regulations:
        lines.append("- 관련 규제·문서 후보:")
        for item in regulatory.applicable_regulations[:15]:
            lines.append(f"  - {item}")
        lines.append("")
    if regulatory.incentives:
        lines.append("- 인센티브·지원 (에이전트 요약):")
        for item in regulatory.incentives:
            lines.append(f"  - {item}")
        lines.append("")
    if regulatory.risks:
        lines.append("- 리스크:")
        for item in regulatory.risks:
            lines.append(f"  - {item}")
        lines.append("")
    if regulatory.source_urls:
        lines.append("- 참고 링크:")
        for u in regulatory.source_urls[:12]:
            lines.append(f"  - {u}")
        lines.append("")
    if regulatory.reason:
        lines.extend(["- **판단 근거 요약 (에이전트):**", "", regulatory.reason, ""])
    if regulatory.extracted_law_candidates:
        lines.append("- 법령·정책명 추출 후보 (2단계):")
        for item in regulatory.extracted_law_candidates[:12]:
            lines.append(f"  - {item}")
        lines.append("")
    if regulatory.pipeline_notes:
        lines.append("- 파이프라인 메모:")
        for n in regulatory.pipeline_notes[:15]:
            lines.append(f"  - {n}")
        lines.append("")
    if regulatory.error:
        lines.append(f"- _에이전트 메모:_ {regulatory.error}")
        lines.append("")
    return "\n".join(lines)


async def run(
    claims: list[Claim],
    scientific: ScientificAgentOutput,
    industrial: IndustrialAgentOutput,
    regulatory: RegulatoryAgentOutput,
    cross_validation: CrossValidatorOutput,
) -> str:
    report_input = ReportInput(
        company_name='SK이노베이션',
        claims=claims,
        scientific=scientific,
        industrial=industrial,
        regulatory=regulatory,
        cross_validation=cross_validation,
    )
    report_output = await generate_report(report_input)
    return report_output.report_markdown
