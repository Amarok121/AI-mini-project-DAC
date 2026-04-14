"""
GRADE 스타일 자동 점수 스켈레톤 (설계 §7.1 가중치).

완전한 GRADE는 임상 맥락·전문가 판단이 필요하므로, 여기서는 메타데이터·초록 키워드 기반 휴리스틱이다.
"""

from __future__ import annotations

import math
import re
from typing import Any, Literal, cast

from app.schemas.agent_result import GradeDimensionScores, PaperResult


def normalize_title(title: str) -> str:
    t = re.sub(r"[^a-z0-9가-힣]+", "", (title or "").lower())
    return t[:100]


# 설계 §7.1 가중치
W_STUDY = 0.30
W_BIAS = 0.20
W_CONS = 0.20
W_DIR = 0.15
W_PREC = 0.10
W_VEN = 0.05


def _study_design_score(title: str, abstract: str) -> float:
    blob = f"{title} {abstract}".lower()
    if any(
        k in blob
        for k in ("systematic review", "meta-analysis", "metaanalysis", "체계적 문헌", "메타분석")
    ):
        return 1.0
    if any(k in blob for k in ("review", "overview", "서베", "리뷰")):
        return 0.75
    if "randomized" in blob or "rct" in blob:
        return 0.7
    if "arxiv" in blob or "preprint" in blob:
        return 0.35
    if any(k in blob for k in ("case study", "pilot study", "pilot-scale")):
        return 0.55
    return 0.5


def _bias_score(citation_count: int) -> float:
    # 인용 수가 많을수록 재현·주목도 힌트 (자동 편향 평가의 대용)
    base = 0.45
    if citation_count >= 200:
        return min(0.95, base + 0.45)
    if citation_count >= 50:
        return min(0.9, base + 0.35)
    if citation_count >= 10:
        return base + 0.2
    return base


def _consistency_score(citation_count: int) -> float:
    return min(1.0, math.log10(citation_count + 1) / 2.5)


def _directness_score(abstract: str, tech_keywords: list[str]) -> float:
    blob = (abstract or "").lower()
    hits = sum(1 for k in tech_keywords if k.lower() in blob)
    return min(1.0, 0.35 + 0.15 * hits)


def _precision_score(citation_count: int) -> float:
    return min(1.0, citation_count / 150.0)


def _venue_score(venue: str) -> float:
    v = (venue or "").lower()
    if "arxiv" in v and "preprint" in v:
        return 0.52
    tier_a = (
        "nature",
        "science",
        "cell",
        "joule",
        "energy environ",
        "nature energy",
        "nature climate",
        "pnas",
    )
    if any(t in v for t in tier_a):
        return 0.95
    if v:
        return 0.6
    return 0.45


def score_unified_paper(
    unified: dict[str, Any],
    *,
    tech_keywords: list[str],
) -> tuple[float, GradeDimensionScores, str]:
    title = str(unified.get("title") or "")
    abstract = str(unified.get("abstract") or "")
    citations = int(unified.get("citations") or 0)
    venue = str(unified.get("venue") or "")

    study_design = _study_design_score(title, abstract)
    bias_risk = _bias_score(citations)
    consistency_hint = _consistency_score(citations)
    directness = _directness_score(abstract, tech_keywords)
    precision_hint = _precision_score(citations)
    venue_authority = _venue_score(venue)

    weighted = (
        W_STUDY * study_design
        + W_BIAS * bias_risk
        + W_CONS * consistency_hint
        + W_DIR * directness
        + W_PREC * precision_hint
        + W_VEN * venue_authority
    )

    gd = GradeDimensionScores(
        study_design=round(study_design, 4),
        bias_risk=round(bias_risk, 4),
        consistency_hint=round(consistency_hint, 4),
        directness=round(directness, 4),
        precision_hint=round(precision_hint, 4),
        venue_authority=round(venue_authority, 4),
        weighted_total=round(weighted, 4),
    )

    if weighted >= 0.75:
        lvl = "HIGH"
    elif weighted >= 0.5:
        lvl = "MED"
    else:
        lvl = "LOW"

    return weighted, gd, lvl


def estimate_trl_from_text(text: str) -> str:
    blob = (text or "").lower()
    if any(x in blob for x in ("commercial deployment", "gw-scale", "industrial scale", "mw-scale")):
        return "TRL 7~9"
    if any(x in blob for x in ("pilot", "demonstration", "field test", "파일럿")):
        return "TRL 5~7"
    if any(x in blob for x in ("laboratory", "lab-scale", "bench", "실험실")):
        return "TRL 3~5"
    return "TRL 2~5"


def average_grade_dimensions(rows: list[GradeDimensionScores]) -> GradeDimensionScores:
    if not rows:
        return GradeDimensionScores()
    n = len(rows)

    def avg(attr: str) -> float:
        return round(sum(getattr(x, attr) for x in rows) / n, 4)

    return GradeDimensionScores(
        study_design=avg("study_design"),
        bias_risk=avg("bias_risk"),
        consistency_hint=avg("consistency_hint"),
        directness=avg("directness"),
        precision_hint=avg("precision_hint"),
        venue_authority=avg("venue_authority"),
        weighted_total=avg("weighted_total"),
    )


def paper_result_from_parts(
    *,
    title: str,
    authors: list[str],
    year: int,
    journal: str,
    url: str,
    grade_score: float,
    grade_level: str,
    citation_count: int,
    abstract: str,
    ss_id: str,
    oa_id: str,
    arxiv_id: str = '',
    doi: str = '',
) -> PaperResult:
    gl = cast(
        Literal["HIGH", "MED", "LOW"],
        grade_level if grade_level in ("HIGH", "MED", "LOW") else "LOW",
    )
    return PaperResult(
        title=title,
        authors=authors,
        year=year,
        journal=journal,
        url=url or "",
        grade_score=round(grade_score, 4),
        grade_level=gl,
        citation_count=citation_count,
        abstract=(abstract or "")[:1200],
        semantic_scholar_id=ss_id,
        openalex_id=oa_id,
        arxiv_id=arxiv_id,
        doi=doi,
    )
