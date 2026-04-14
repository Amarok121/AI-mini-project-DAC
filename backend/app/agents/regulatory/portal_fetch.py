"""
Step 3: 정부·공공 포털에서 원문/요약 텍스트 fetch (가능한 범위).

- 국가법령정보센터: OC 키 필요 (LAW_GO_KR_API_KEY)
- Federal Register: 공개 JSON API
- EU: 공식 REST가 복잡해, Tavily 히트 중 eur-lex/europa.eu URL 스니펫을 대체 원문으로 사용
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import Optional

import httpx

from app.core.config import settings

from app.agents.regulatory.tavily_search import TavilyHit
from app.agents.regulatory.eurlex import try_fetch_eu_from_sources

logger = logging.getLogger(__name__)

_LAW_DETAIL_URL = "https://www.law.go.kr/DRF/lawService.do"


@dataclass
class PortalDocument:
    law_name: str
    source: str
    text: str
    url: str = ""
    pdf_url: str = ""


def _has_korean(s: str) -> bool:
    return bool(re.search(r"[\uac00-\ud7a3]", s))


def _classify_law_name(name: str) -> str:
    n = name.upper()
    if _has_korean(name) or "법" in name or "시행령" in name or "시행규칙" in name:
        return "KR"
    if any(
        k in n
        for k in (
            "IRA",
            "45Q",
            "EPA",
            "FEDERAL",
            "U.S.C",
            "CFR",
            "UNITED STATES",
            "US ",
            "TREASURY",
            "IRS",
        )
    ):
        return "US"
    if any(
        k in n
        for k in (
            "EU ",
            "EUR",
            "CBAM",
            "REGULATION (EU)",
            "DIRECTIVE",
            "EEC ",
            "CELEX",
        )
    ):
        return "EU"
    return "UNK"


def _flatten_law_service_json(data: dict) -> str:
    """lawService JSON에서 사람이 읽을 수 있는 요약 문자열 추출 (버전별 차이 흡수)."""
    if not isinstance(data, dict):
        return ""
    # 흔한 키 후보
    for key in ("LawService", "lawService", "법령", "Law"):
        block = data.get(key)
        if isinstance(block, dict):
            parts: list[str] = []
            for k in ("법령명한글", "법령명약칭", "공포일자", "시행일자", "소관부처명"):
                if k in block:
                    parts.append(f"{k}: {block[k]}")
            if "조문" in block or "조문단위" in block:
                parts.append("(조문 데이터 포함 — 일부만 표시)")
            if parts:
                return "\n".join(parts)[:10000]
    return json.dumps(data, ensure_ascii=False)[:12000]


def _fetch_law_detail_sync(oc: str, mst: str) -> str:
    """법령일련번호(MST)로 lawService 상세(JSON)."""
    mst = (mst or "").strip()
    if not mst:
        return ""
    params = {
        "OC": oc,
        "target": "law",
        "MST": mst,
        "type": "JSON",
    }
    try:
        with httpx.Client(timeout=25.0) as client:
            r = client.get(_LAW_DETAIL_URL, params=params)
            r.raise_for_status()
            data = r.json()
    except (httpx.HTTPError, json.JSONDecodeError, ValueError) as e:
        logger.info("law.go.kr lawService failed MST=%s: %s", mst, e)
        return ""
    return _flatten_law_service_json(data) if isinstance(data, dict) else str(data)[:12000]


def _fetch_law_go_kr_sync(keyword: str) -> tuple[str, str]:
    oc = (settings.LAW_GO_KR_API_KEY or "").strip()
    if not oc:
        return "", ""
    url = "https://www.law.go.kr/DRF/lawSearch.do"
    params = {
        "OC": oc,
        "target": "law",
        "type": "JSON",
        "query": keyword[:200],
        "display": 5,
    }
    try:
        with httpx.Client(timeout=20.0) as client:
            r = client.get(url, params=params)
            r.raise_for_status()
            data = r.json()
    except (httpx.HTTPError, json.JSONDecodeError, ValueError) as e:
        logger.info("law.go.kr fetch failed for %s: %s", keyword, e)
        return "", ""

    law_block = data.get("LawSearch") or data.get("lawSearch") or {}
    items = law_block.get("law") or law_block.get("Law") or []
    if isinstance(items, dict):
        items = [items]
    if not isinstance(items, list):
        return json.dumps(data, ensure_ascii=False)[:12000], "https://www.law.go.kr"

    chunks: list[str] = []
    for it in items[:5]:
        if not isinstance(it, dict):
            continue
        title = it.get("법령명한글") or it.get("lawName") or it.get("nm") or ""
        lid = it.get("법령ID") or it.get("lawId") or ""
        mst = it.get("법령일련번호") or it.get("MST") or ""
        dept = it.get("소관부처명") or ""
        line = f"### {title}\n- 법령ID: {lid} | 소관: {dept}\n"
        if mst:
            detail = _fetch_law_detail_sync(oc, str(mst))
            if detail:
                line += "\n--- 상세(법령일련번호 기준) ---\n" + detail[:9000] + "\n"
            else:
                line += f"- 법령일련번호: {mst} (상세 본문은 API 응답 형식 확인 필요)\n"
        chunks.append(line)

    text = "\n".join(chunks) if chunks else json.dumps(data, ensure_ascii=False)[:8000]
    return text, "https://www.law.go.kr"


def _fetch_federal_register_sync(keyword: str) -> tuple[str, str, str]:
    url = "https://www.federalregister.gov/api/v1/documents.json"
    params = {"per_page": 5, "order": "relevance", "conditions[term]": keyword[:256]}
    try:
        with httpx.Client(timeout=20.0) as client:
            r = client.get(url, params=params)
            r.raise_for_status()
            data = r.json()
    except (httpx.HTTPError, json.JSONDecodeError) as e:
        logger.info("Federal Register fetch failed for %s: %s", keyword, e)
        return "", "", ""

    results = data.get("results") or []
    chunks: list[str] = []
    first_url = ""
    first_pdf = ""
    for doc in results[:5]:
        if not isinstance(doc, dict):
            continue
        title = doc.get("title") or ""
        abstract = doc.get("abstract") or ""
        pdf_u = (doc.get("pdf_url") or "").strip()
        html_url = doc.get("html_url") or pdf_u or ""
        if not first_url and html_url:
            first_url = html_url
        if not first_pdf and pdf_u:
            first_pdf = pdf_u
        chunks.append(f"### {title}\n{abstract}\nURL: {html_url}\nPDF: {pdf_u}\n")
    return "\n".join(chunks)[:16000], first_url, first_pdf


def _eu_from_tavily_hits(law_name: str, hits: list[TavilyHit]) -> tuple[str, str]:
    """EUR-Lex 직접 파싱 대신, Tavily가 이미 가져온 공식 도메인 스니펫을 근거로 사용."""
    tokens = [t for t in re.findall(r"[A-Za-z가-힣0-9]+", law_name.lower()) if len(t) > 2]
    best = ""
    best_url = ""
    best_score = -1
    for h in hits:
        u = (h.url or "").lower()
        if "eur-lex" not in u and "europa.eu" not in u:
            continue
        blob = f"{h.title} {h.content}".lower()
        score = sum(1 for t in tokens if t in blob) + min(len(h.content), 2000) // 500
        block = f"{h.title}\n{h.content}\nURL: {h.url}"
        if score > best_score or (score == best_score and len(block) > len(best)):
            best, best_url, best_score = block, h.url, score
    return best[:12000], best_url


def fetch_portal_documents_sync(
    law_names: list[str],
    tavily_hits: list[TavilyHit],
) -> tuple[list[PortalDocument], list[str]]:
    """법령 후보별로 포털(또는 Tavily EU 대체) 텍스트 수집."""
    notes: list[str] = []
    docs: list[PortalDocument] = []
    seen: set[str] = set()

    for raw_name in law_names[:8]:
        key = raw_name.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)

        region = _classify_law_name(raw_name)
        if region == "KR":
            text, url = _fetch_law_go_kr_sync(raw_name)
            if not text:
                notes.append(f"[KR] '{raw_name}': law.go.kr 결과 없음 또는 OC 키 미설정")
                continue
            docs.append(
                PortalDocument(
                    law_name=raw_name,
                    source="law.go.kr",
                    text=text,
                    url=url,
                )
            )
            notes.append(f"[KR] '{raw_name}': law.go.kr 검색 요약 수집")
        elif region == "US":
            text, url, pdf_fr = _fetch_federal_register_sync(raw_name)
            if not text:
                notes.append(f"[US] '{raw_name}': Federal Register 결과 없음")
                continue
            docs.append(
                PortalDocument(
                    law_name=raw_name,
                    source="federalregister.gov",
                    text=text,
                    url=url,
                    pdf_url=pdf_fr,
                )
            )
            notes.append(f"[US] '{raw_name}': Federal Register 요약 수집")
        elif region == "EU":
            eu_text, eu_url, celex = try_fetch_eu_from_sources(raw_name, tavily_hits)
            if eu_text:
                label = f"eur-lex (CELEX {celex})" if celex else "eur-lex"
                pdf_eu = ""
                if celex:
                    pdf_eu = f"https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:{celex}"
                docs.append(
                    PortalDocument(
                        law_name=raw_name,
                        source=label,
                        text=eu_text,
                        url=eu_url or "",
                        pdf_url=pdf_eu,
                    )
                )
                notes.append(f"[EU] '{raw_name}': EUR-Lex 본문 fetch ({celex or 'CELEX 미상'})")
                continue
            text, url = _eu_from_tavily_hits(raw_name, tavily_hits)
            if not text:
                notes.append(f"[EU] '{raw_name}': CELEX·Tavily eur-lex 모두 없음")
                continue
            docs.append(
                PortalDocument(
                    law_name=raw_name,
                    source="eur-lex (Tavily snippet fallback)",
                    text=text,
                    url=url,
                )
            )
            notes.append(f"[EU] '{raw_name}': EUR-Lex 스니펫 폴백")
        else:
            notes.append(f"[?] '{raw_name}': 지역 분류 불명 — 스킵")

    return docs, notes


async def fetch_portal_documents(
    law_names: list[str],
    tavily_hits: list[TavilyHit],
) -> tuple[list[PortalDocument], list[str]]:
    return await asyncio.to_thread(fetch_portal_documents_sync, law_names, tavily_hits)
