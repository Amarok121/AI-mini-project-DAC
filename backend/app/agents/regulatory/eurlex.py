"""EUR-Lex: CELEX 추출 및 법령 본문(HTML→간단 텍스트) fetch."""

from __future__ import annotations

import logging
import re
from html import unescape
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# URL·텍스트에서 CELEX 후보 (예: 32023R0956, 32019R1009)
_CELEX_RE = re.compile(
    r"(?:CELEX[:\s]*|uri=CELEX:)(\d{4}[A-Z]\d{4,})",
    re.IGNORECASE,
)
# 일부 URL은 celex= 형태
_CELEX_ALT = re.compile(r"celex=([0-9]{4}[A-Z][0-9]{4,})", re.IGNORECASE)


def extract_celex_from_url_or_text(s: str) -> Optional[str]:
    if not s:
        return None
    for rx in (_CELEX_RE, _CELEX_ALT):
        m = rx.search(s)
        if m:
            return m.group(1).upper()
    return None


def _strip_html(html: str, max_chars: int = 18000) -> str:
    text = re.sub(r"(?s)<script[^>]*>.*?</script>", " ", html, flags=re.I)
    text = re.sub(r"(?s)<style[^>]*>.*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


def fetch_celex_document(
    celex: str,
    *,
    lang: str = "EN",
) -> tuple[str, str]:
    """
    CELEX로 EUR-Lex HTML 본문을 받아 평문으로 축약.
    반환: (text, canonical_url)
    """
    c = (celex or "").strip().upper()
    if not re.match(r"^\d{4}[A-Z]\d{4,}$", c):
        return "", ""

    url = f"https://eur-lex.europa.eu/legal-content/{lang}/TXT/HTML/?uri=CELEX:{c}"
    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            r = client.get(
                url,
                headers={"User-Agent": "AI-mini-project-DAC/1.0 (research)"},
            )
            if r.status_code == 404:
                url_txt = f"https://eur-lex.europa.eu/legal-content/{lang}/TXT/?uri=CELEX:{c}"
                r = client.get(
                    url_txt,
                    headers={"User-Agent": "AI-mini-project-DAC/1.0 (research)"},
                )
            r.raise_for_status()
            plain = _strip_html(r.text)
            return plain, url
    except httpx.HTTPError as e:
        logger.info("EUR-Lex fetch failed for CELEX %s: %s", c, e)
        return "", ""


def try_fetch_eu_from_sources(
    law_name: str,
    tavily_hits: list,
) -> tuple[str, str, Optional[str]]:
    """
    1) law_name / Tavily URL에서 CELEX 추출 후 본문 fetch
    2) 실패 시 빈 문자열
    반환: (text, page_url, celex_or_none)
    """
    candidates: list[str] = [law_name]
    for h in tavily_hits:
        candidates.extend(
            [
                str(getattr(h, "url", "") or ""),
                str(getattr(h, "title", "") or ""),
                str(getattr(h, "content", "") or ""),
            ]
        )

    celex: Optional[str] = None
    for s in candidates:
        celex = extract_celex_from_url_or_text(s)
        if celex:
            break

    if not celex:
        return "", "", None

    text, page_url = fetch_celex_document(celex)
    if text:
        return text, page_url or "", celex
    return "", "", celex
