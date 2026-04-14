from __future__ import annotations

import asyncio
from collections.abc import Iterable
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

import httpx

from app.core.config import settings


PUBLICATION_SERVICE = 'patUtiModInfoSearchSevice'
CITATION_SERVICE = 'CitationService'


async def search_publication_patents(query: str, display: int = 10) -> list[dict]:
    params = {
        'word': query,
        'year': '0',
        'patent': 'true',
        'utility': 'true',
        'numOfRows': max(1, min(display, 50)),
        'pageNo': 1,
        'ServiceKey': settings.KIPRIS_API_KEY,
    }
    payload = await _get_xml(
        f'{_publication_base_url()}/{PUBLICATION_SERVICE}/getWordSearch',
        params=params,
    )
    return _extract_items(payload)


async def fetch_prosecution_history(application_number: str) -> list[dict]:
    params = {
        'applicationNumber': application_number,
        'ServiceKey': settings.KIPRIS_API_KEY,
    }
    payload = await _get_xml(
        f'{_publication_base_url()}/{PUBLICATION_SERVICE}/patentLegalStatusInfo',
        params=params,
    )
    return _extract_items(payload)


async def fetch_citation_records(application_number: str) -> list[dict]:
    params = {
        'applicationNumber': application_number,
        'ServiceKey': settings.KIPRIS_API_KEY,
    }
    payload = await _get_xml(
        f'{_citation_base_url()}/{CITATION_SERVICE}/citationInfoV3',
        params=params,
    )
    return _extract_items(payload)


async def fetch_patent_text_bundle(application_number: str) -> dict:
    """
    초록/청구항이 검색 API 응답에 없을 때 상세 API를 재조회해 텍스트를 보강한다.
    KIPRIS Plus 상품/계약 범위에 따라 일부 엔드포인트는 비어 있거나 실패할 수 있으므로
    다중 경로를 순차 시도하고, 가능한 값만 반환한다.
    """
    if not application_number:
        return {}

    # 1) 서지/상세 계열 조회
    detail_items = await gather_first_non_empty(
        _safe_items(
            f'{_publication_base_url()}/{PUBLICATION_SERVICE}/patentBibliographicInfo',
            {'applicationNumber': application_number, 'ServiceKey': settings.KIPRIS_API_KEY},
        ),
        _safe_items(
            f'{_publication_base_url()}/{PUBLICATION_SERVICE}/patentDetailInfo',
            {'applicationNumber': application_number, 'ServiceKey': settings.KIPRIS_API_KEY},
        ),
        _safe_items(
            f'{_publication_base_url()}/{PUBLICATION_SERVICE}/patentImageAndFullTextInfo',
            {'applicationNumber': application_number, 'ServiceKey': settings.KIPRIS_API_KEY},
        ),
    )

    # 2) 초록/요약 전용 계열 조회
    abstract_items = await gather_first_non_empty(
        _safe_items(
            f'{_publication_base_url()}/{PUBLICATION_SERVICE}/patentAbstractInfo',
            {'applicationNumber': application_number, 'ServiceKey': settings.KIPRIS_API_KEY},
        ),
        _safe_items(
            f'{_publication_base_url()}/{PUBLICATION_SERVICE}/patentSummaryInfo',
            {'applicationNumber': application_number, 'ServiceKey': settings.KIPRIS_API_KEY},
        ),
    )

    # 3) 청구항 계열 조회
    claim_items = await gather_first_non_empty(
        _safe_items(
            f'{_publication_base_url()}/{PUBLICATION_SERVICE}/patentClaimInfo',
            {'applicationNumber': application_number, 'ServiceKey': settings.KIPRIS_API_KEY},
        ),
        _safe_items(
            f'{_publication_base_url()}/{PUBLICATION_SERVICE}/patentClaimTextInfo',
            {'applicationNumber': application_number, 'ServiceKey': settings.KIPRIS_API_KEY},
        ),
    )

    abstract = _pick_text_from_items(
        [*detail_items, *abstract_items],
        'abstract',
        'koreanAbstract',
        'engAbstract',
        'summary',
        'abstractText',
        'inventionPurpose',
        'techProblem',
        'meansForSolution',
        'effectOfInvention',
    )
    claim_text = _pick_text_from_items(
        [*claim_items, *detail_items],
        'claim',
        'claimText',
        'claimSummary',
        'independentClaim',
        'mainClaim',
    )

    bundle = {
        'abstract': abstract,
        'claim_text': claim_text,
    }
    return {k: v for k, v in bundle.items() if v}


async def _get_xml(url: str, params: dict) -> ET.Element:
    if not settings.KIPRIS_API_KEY:
        raise RuntimeError('KIPRIS API key is not configured')

    async with httpx.AsyncClient(timeout=settings.API_TIMEOUT_SEC) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()

    return ET.fromstring(response.text)


async def _safe_items(url: str, params: dict) -> list[dict]:
    try:
        payload = await _get_xml(url, params=params)
        return _extract_items(payload)
    except Exception:
        return []


def _publication_base_url() -> str:
    return _normalize_base_url(settings.KIPRIS_API_URL, fallback='http://plus.kipris.or.kr/kipo-api/kipi')


def _citation_base_url() -> str:
    return _normalize_base_url(settings.KIPRIS_API_URL, fallback='http://plus.kipris.or.kr/openapi/rest', force_openapi=True)


def _normalize_base_url(raw_url: str, fallback: str, force_openapi: bool = False) -> str:
    if not raw_url:
        return fallback

    parsed = urlparse(raw_url)
    if not parsed.scheme or not parsed.netloc:
        return fallback

    base = f'{parsed.scheme}://{parsed.netloc}'
    path = parsed.path.rstrip('/')

    if force_openapi:
        if 'openapi/rest' in path:
            return f'{base}/openapi/rest'
        return f'{base}/openapi/rest'

    if 'kipo-api/kipi' in path:
        return f'{base}/kipo-api/kipi'
    if 'openapi/rest' in path:
        return f'{base}/openapi/rest'
    return fallback


def _extract_items(root: ET.Element) -> list[dict]:
    items: list[dict] = []

    for element in root.iter():
        tag = _normalize_tag(element.tag)
        if tag in {'item', 'patent', 'application', 'citation', 'result'}:
            item = _element_to_dict(element)
            if item:
                items.append(item)

    if items:
        return items

    flat = _element_to_dict(root)
    return [flat] if flat else []


def _element_to_dict(element: ET.Element) -> dict:
    data: dict[str, object] = {}

    children = list(element)
    if not children:
        text = (element.text or '').strip()
        if text:
            return {_normalize_tag(element.tag): text}
        return {}

    for child in children:
        key = _normalize_tag(child.tag)
        value = _element_to_dict(child)
        if len(value) == 1 and key in value:
            payload = value[key]
        elif value:
            payload = value
        else:
            payload = (child.text or '').strip()

        if key in data:
            existing = data[key]
            if isinstance(existing, list):
                existing.append(payload)
            else:
                data[key] = [existing, payload]
        else:
            data[key] = payload

    return data


def _normalize_tag(tag: str) -> str:
    return tag.split('}')[-1].strip().lower()


def pick_first(item: dict, *keys: str, default: str = '') -> str:
    normalized = {_normalize_tag(str(key)): value for key, value in item.items()}
    for key in keys:
        value = normalized.get(_normalize_tag(key))
        if isinstance(value, str) and value.strip():
            return value.strip()
        if value not in (None, '', []):
            return str(value)
    return default


def pick_bool(item: dict, *keys: str, default: bool = False) -> bool:
    value = pick_first(item, *keys, default='')
    if not value:
        return default
    return value.lower() in {'y', 'yes', 'true', '1', '등록', 'yes'}


async def gather_first_non_empty(*calls: asyncio.Future) -> list[dict]:
    results = await asyncio.gather(*calls, return_exceptions=True)
    for result in results:
        if isinstance(result, list) and result:
            return result
    return []


def _pick_text_from_items(items: list[dict], *keys: str) -> str:
    for item in items:
        value = pick_first(item, *keys, default='')
        if value and len(value.strip()) > 10:
            return value.strip()
    return ''
