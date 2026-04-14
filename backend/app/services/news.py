from __future__ import annotations

import html
import json
import re
from html import unescape
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx

from app.core.config import settings


_TAG_RE = re.compile(r'<[^>]+>')


async def search_naver_news(query: str, display: int = 10, start: int = 1) -> list[dict]:
    if not settings.NAVER_CLIENT_ID or not settings.NAVER_CLIENT_SECRET:
        raise RuntimeError('Naver News API credentials are not configured')

    headers = {
        'X-Naver-Client-Id': settings.NAVER_CLIENT_ID,
        'X-Naver-Client-Secret': settings.NAVER_CLIENT_SECRET,
        'Accept': 'application/json',
    }
    params = {
        'query': query,
        'display': max(1, min(display, 100)),
        'start': max(1, min(start, 1000)),
        'sort': 'date',
    }

    async with httpx.AsyncClient(timeout=settings.API_TIMEOUT_SEC) as client:
        response = await client.get(
            settings.NAVER_NEWS_API_URL,
            headers=headers,
            params=params,
        )
        response.raise_for_status()
        payload = response.json()

    items = payload.get('items', [])
    return [_normalize_item(item) for item in items if item]


async def fetch_news_article_text(url: str) -> str:
    content = await fetch_news_article_content(url)
    return content.get('text', '')


async def fetch_news_article_content(url: str) -> dict[str, str]:
    if not url:
        return {'text': '', 'trace': '입력 URL 없음', 'final_url': ''}

    traces: list[str] = []
    last_exception: str | None = None
    for candidate_url in _build_candidate_urls(url):
        try:
            async with httpx.AsyncClient(timeout=settings.API_TIMEOUT_SEC, follow_redirects=True) as client:
                response = await client.get(
                    candidate_url,
                    headers={
                        'User-Agent': (
                            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                            'AppleWebKit/537.36 (KHTML, like Gecko) '
                            'Chrome/124.0.0.0 Safari/537.36'
                        ),
                        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
                    },
                )
                response.raise_for_status()
            text = _extract_best_article_text(response.text)
            if text:
                traces.append(f'성공:{candidate_url}')
                return {
                    'text': text,
                    'trace': ' -> '.join(traces[-4:]),
                    'final_url': str(response.url),
                }
            traces.append(f'본문부족:{candidate_url}')
        except Exception as exc:
            last_exception = str(exc)
            traces.append(f'실패:{candidate_url}')

    if last_exception:
        traces.append(f'최종오류:{last_exception}')
    return {
        'text': '',
        'trace': ' -> '.join(traces[-6:]) or '본문 추출 실패',
        'final_url': '',
    }


def _normalize_item(item: dict) -> dict:
    origin_link = _pick_first_non_empty(item.get('originallink'))
    naver_link = _pick_first_non_empty(item.get('link'))
    selected_link = _pick_first_non_empty(origin_link, naver_link)
    title = _clean_text(item.get('title', ''))
    description = _clean_text(item.get('description', ''))
    published_at = _normalize_pub_date(item.get('pubDate', ''))

    return {
        'title': title,
        'description': description,
        'url': selected_link,
        'origin_url': origin_link,
        'naver_url': naver_link,
        'provider': _extract_provider(selected_link),
        'published_at': published_at,
    }


def _clean_text(text: str) -> str:
    text = html.unescape(text or '')
    return _TAG_RE.sub('', text).strip()


def _pick_first_non_empty(*values: str | None) -> str:
    for value in values:
        if value and value.strip():
            return value.strip()
    return ''


def _extract_provider(url: str) -> str:
    if not url:
        return 'naver.com'
    hostname = urlparse(url).hostname or ''
    return hostname.replace('www.', '') or 'naver.com'


def _normalize_pub_date(raw_value: str) -> str:
    if not raw_value:
        return ''

    try:
        dt = parsedate_to_datetime(raw_value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.date().isoformat()
    except Exception:
        pass

    for fmt in ('%Y-%m-%d', '%Y.%m.%d', '%Y/%m/%d'):
        try:
            return datetime.strptime(raw_value.strip(), fmt).date().isoformat()
        except ValueError:
            continue

    return raw_value.strip()


def _extract_article_text(html_text: str) -> str:
    if not html_text:
        return ''

    text = html_text
    text = re.sub(r'(?is)<script[^>]*>.*?</script>', ' ', text)
    text = re.sub(r'(?is)<style[^>]*>.*?</style>', ' ', text)
    text = re.sub(r'(?is)<noscript[^>]*>.*?</noscript>', ' ', text)
    text = re.sub(r'(?is)<header[^>]*>.*?</header>', ' ', text)
    text = re.sub(r'(?is)<footer[^>]*>.*?</footer>', ' ', text)
    text = re.sub(r'(?is)<nav[^>]*>.*?</nav>', ' ', text)
    text = re.sub(r'(?is)<aside[^>]*>.*?</aside>', ' ', text)
    text = re.sub(r'(?is)<(div|section|article|p|span|li|h1|h2|h3|h4|h5|h6)[^>]*>', '\n', text)
    text = _TAG_RE.sub(' ', text)
    text = unescape(text)
    text = re.sub(r'\s+', ' ', text)

    lines = []
    for chunk in re.split(r'(?<=[.!?])\s+|\n+', text):
        cleaned = chunk.strip()
        if len(cleaned) >= 20:
            lines.append(cleaned)

    if not lines:
        return ''

    return '\n'.join(lines[:120])


def _extract_best_article_text(html_text: str) -> str:
    candidates = [
        _extract_ld_json_article_body(html_text),
        _extract_semantic_article_body(html_text),
        _extract_article_text(html_text),
    ]
    cleaned = [c.strip() for c in candidates if c and c.strip()]
    if not cleaned:
        return ''
    # 가장 설명력이 높은 본문을 선택한다.
    return max(cleaned, key=len)


def _extract_semantic_article_body(html_text: str) -> str:
    patterns = [
        r'(?is)<article[^>]*>(.*?)</article>',
        r'(?is)<main[^>]*>(.*?)</main>',
        r'(?is)<div[^>]+(?:id|class)=["\'][^"\']*(?:article|content|news|body|post)[^"\']*["\'][^>]*>(.*?)</div>',
    ]
    chunks: list[str] = []
    for pattern in patterns:
        for match in re.findall(pattern, html_text):
            text = _extract_article_text(match)
            if len(text) >= 180:
                chunks.append(text)
    if not chunks:
        return ''
    return max(chunks, key=len)


def _extract_ld_json_article_body(html_text: str) -> str:
    scripts = re.findall(
        r'(?is)<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html_text,
    )
    if not scripts:
        return ''

    candidates: list[str] = []
    for raw in scripts:
        parsed = _parse_json_safely(raw)
        if parsed is None:
            continue
        for body in _find_article_bodies(parsed):
            cleaned = ' '.join(str(body).split())
            if len(cleaned) >= 80:
                candidates.append(cleaned)
    if not candidates:
        return ''
    return max(candidates, key=len)


def _parse_json_safely(raw: str):
    text = (raw or '').strip()
    if not text:
        return None
    text = html.unescape(text)
    try:
        return json.loads(text)
    except Exception:
        return None


def _find_article_bodies(payload) -> list[str]:
    results: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_l = str(key).lower()
            if key_l in {'articlebody', 'description'} and isinstance(value, str):
                results.append(value)
            else:
                results.extend(_find_article_bodies(value))
    elif isinstance(payload, list):
        for item in payload:
            results.extend(_find_article_bodies(item))
    return results


def _build_candidate_urls(url: str) -> list[str]:
    if not url:
        return []
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return [url]

    base = _strip_tracking_params(url)
    candidates = [base]

    host = parsed.netloc.lower()
    if 'm.' in host:
        desktop_host = host.replace('m.', 'www.', 1)
        candidates.append(_replace_netloc(base, desktop_host))
    elif host.startswith('www.'):
        mobile_host = host.replace('www.', 'm.', 1)
        candidates.append(_replace_netloc(base, mobile_host))

    # AMP/print 타입 URL을 지원하는 사이트가 있어 변형 시도
    if not base.endswith('/amp'):
        candidates.append(base.rstrip('/') + '/amp')
    if '?' in base:
        candidates.append(base + '&output=1')
    else:
        candidates.append(base + '?output=1')

    deduped: list[str] = []
    for candidate in candidates:
        if candidate and candidate not in deduped:
            deduped.append(candidate)
    return deduped


def _strip_tracking_params(url: str) -> str:
    parsed = urlparse(url)
    params = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        key_l = key.lower()
        if key_l.startswith('utm_'):
            continue
        if key_l in {'fbclid', 'gclid', 'mc_cid', 'mc_eid'}:
            continue
        params.append((key, value))
    return urlunparse(parsed._replace(query=urlencode(params, doseq=True)))


def _replace_netloc(url: str, new_netloc: str) -> str:
    parsed = urlparse(url)
    return urlunparse(parsed._replace(netloc=new_netloc))
