"""arXiv Atom API: 프리프린트 검색 (무료, API 키 불필요).

공식 안내: https://arxiv.org/help/api/user-manual

엔드포인트: ``GET https://export.arxiv.org/api/query``

주요 파라미터
------------
- ``search_query``: ``ti:``, ``abs:``, ``au:``, ``cat:``, ``all:`` 필드와
  ``AND`` / ``OR`` / ``NOT`` 조합. 공백은 URL 인코딩 시 ``+`` 로 전달 가능.
- ``start``, ``max_results`` (기본 10).
- ``sortBy``: ``relevance``, ``lastUpdatedDate``, ``submittedDate``.

응답은 Atom XML(``entry`` 목록). 각 항목에 ``title``, ``summary``(초록),
``published``, 저자, ``arxiv:doi``, ``arxiv:journal_ref`` 등이 포함될 수 있음.

공정 사용: 연속 다량 요청 시 요청 간 약 3초 간격을 권장. User-Agent에
연락용 이메일을 넣는 것이 좋음 (본 프로젝트는 ``OPENALEX_CONTACT_EMAIL`` 재사용).
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import urlencode

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

ARXIV_API = "https://export.arxiv.org/api/query"
ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV = "{http://arxiv.org/schemas/atom}"


def build_arxiv_search_query(text: str) -> str:
    """영숫자 토큰만 뽑아 ``all:`` … `` AND `` … 형태로 구성 (OR 분할 방지)."""
    raw = (text or "").lower()
    tokens = re.findall(r"[a-z0-9]{3,}", raw)
    stop = {
        "the",
        "and",
        "for",
        "with",
        "from",
        "this",
        "that",
        "are",
        "was",
        "has",
        "not",
        "but",
        "can",
        "may",
        "use",
        "using",
    }
    toks = [t for t in tokens if t not in stop][:6]
    if not toks:
        toks = ["review"]
    parts = [f"all:{t}" for t in toks]
    if len(parts) == 1:
        return parts[0]
    return " AND ".join(parts)


def _clean_text(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def _abs_id_from_entry_id(id_url: str) -> str:
    if "/abs/" in id_url:
        return id_url.split("/abs/", 1)[-1].split("?", 1)[0].strip()
    return ""


def _parse_feed(xml_bytes: bytes) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_bytes)
    out: list[dict[str, Any]] = []
    for entry in root.findall(f"{ATOM}entry"):
        id_el = entry.find(f"{ATOM}id")
        title_el = entry.find(f"{ATOM}title")
        summary_el = entry.find(f"{ATOM}summary")
        published_el = entry.find(f"{ATOM}published")
        if id_el is None or title_el is None:
            continue
        id_url = (id_el.text or "").strip()
        title = _clean_text(title_el.text or "")
        abstract = _clean_text((summary_el.text if summary_el is not None else "") or "")
        year = 0
        if published_el is not None and published_el.text:
            m = re.match(r"(\d{4})", published_el.text.strip())
            if m:
                year = int(m.group(1))
        authors: list[str] = []
        for auth in entry.findall(f"{ATOM}author"):
            ne = auth.find(f"{ATOM}name")
            if ne is not None and ne.text:
                authors.append(_clean_text(ne.text))
        doi_el = entry.find(f"{ARXIV}doi")
        doi = _clean_text((doi_el.text if doi_el is not None else "") or "")
        jr_el = entry.find(f"{ARXIV}journal_ref")
        journal_ref = _clean_text((jr_el.text if jr_el is not None else "") or "")
        link_abs = ""
        for lk in entry.findall(f"{ATOM}link"):
            if lk.get("rel") == "alternate" and lk.get("href"):
                link_abs = lk.get("href") or ""
                break
        aid = _abs_id_from_entry_id(id_url)
        out.append(
            {
                "title": title,
                "abstract": abstract,
                "year": year,
                "authors": authors[:20],
                "doi": doi,
                "journal_ref": journal_ref,
                "abs_url": link_abs or id_url,
                "arxiv_id": aid,
            }
        )
    return out


def search_preprints(query_text: str, *, limit: int = 10) -> list[dict[str, Any]]:
    """검색어(자연어)를 arXiv 쿼리로 바꿔 프리프린트 메타데이터 목록을 반환."""
    sq = build_arxiv_search_query(query_text)
    if not sq:
        return []
    params = {
        "search_query": sq,
        "start": 0,
        "max_results": min(max(limit, 1), 50),
        "sortBy": "relevance",
    }
    url = f"{ARXIV_API}?{urlencode(params)}"
    mail = (settings.OPENALEX_CONTACT_EMAIL or "dev@localhost").strip()
    headers = {"User-Agent": f"AI-mini-project-DAC/1.0 (mailto:{mail})"}
    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.get(url, headers=headers)
            r.raise_for_status()
            return _parse_feed(r.content)
    except (httpx.HTTPError, ET.ParseError, ValueError) as e:
        logger.info("arXiv search failed: %s", e)
        return []
