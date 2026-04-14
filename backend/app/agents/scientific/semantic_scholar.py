"""Semantic Scholar Graph API: 논문 검색 (무료, API 키 선택)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

SS_SEARCH = "https://api.semanticscholar.org/graph/v1/paper/search"


def search_papers(query: str, *, limit: int = 8) -> list[dict[str, Any]]:
    """검색어로 논문 메타데이터 목록 반환. 실패 시 빈 리스트."""
    q = (query or "").strip()[:500]
    if not q:
        return []

    params = {
        "query": q,
        "limit": min(limit, 20),
        "fields": (
            "title,abstract,year,authors,venue,citationCount,"
            "externalIds,openAccessPdf,url,paperId"
        ),
    }
    headers: dict[str, str] = {}
    key = (settings.SEMANTIC_SCHOLAR_API_KEY or "").strip()
    if key:
        headers["x-api-key"] = key

    try:
        with httpx.Client(timeout=25.0) as client:
            r = client.get(SS_SEARCH, params=params, headers=headers)
            if r.status_code == 429:
                logger.warning("Semantic Scholar rate limited")
                return []
            r.raise_for_status()
            data = r.json()
    except (httpx.HTTPError, ValueError) as e:
        logger.info("Semantic Scholar search failed: %s", e)
        return []

    raw = data.get("data") or []
    out: list[dict[str, Any]] = []
    for p in raw:
        if isinstance(p, dict):
            out.append(p)
    return out
