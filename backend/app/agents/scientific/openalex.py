"""OpenAlex API: 논문 검색·보강 메타 (무료, User-Agent에 연락처 권장)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

OPENALEX_BASE = "https://api.openalex.org"


def _ua_headers() -> dict[str, str]:
    mail = (settings.OPENALEX_CONTACT_EMAIL or "dev@localhost").strip()
    return {"User-Agent": f"AI-mini-project-DAC/1.0 (mailto:{mail})"}


def search_works(query: str, *, per_page: int = 8) -> list[dict[str, Any]]:
    """OpenAlex works 검색."""
    q = (query or "").strip()[:500]
    if not q:
        return []
    params = {"search": q, "per_page": min(per_page, 25)}
    try:
        with httpx.Client(timeout=25.0) as client:
            r = client.get(
                f"{OPENALEX_BASE}/works",
                params=params,
                headers=_ua_headers(),
            )
            r.raise_for_status()
            data = r.json()
    except (httpx.HTTPError, ValueError) as e:
        logger.info("OpenAlex search failed: %s", e)
        return []

    results = data.get("results") or []
    out: list[dict[str, Any]] = []
    for w in results:
        if isinstance(w, dict):
            out.append(w)
    return out
