"""
LLM 기반 Scientific(논문) 등급 판정.

- 휴리스틱 점수(grade_evaluator)는 retrieval/초기 랭킹에만 쓰고,
  최종 grade_level/overall_grade는 LLM이 규칙 기반으로 판정한다.
- 반드시 근거(excerpt)를 포함해 JSON으로 반환하도록 강제한다.
"""

from __future__ import annotations

import logging
from typing import Any, Literal, Tuple

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate

from app.core.config import settings
from app.schemas.claim import Claim
from app.schemas.agent_result import PaperResult

from app.agents.langchain_setup import get_chat_model

logger = logging.getLogger(__name__)


_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (
                "You are a strict, evidence-bound scientific auditor. Your job here is PAPER CREDIBILITY grading.\n"
                "This grade is about the paper's own evidentiary strength (study design, methods detail, validation),\n"
                "NOT whether it proves a specific product claim.\n"
                "\n"
                "Rules:\n"
                "1) Use ONLY the provided title/abstract and `pdf_evidence_snippet` (when present). Do NOT invent results.\n"
                "2) Prefer concrete methods/results evidence over vague claims.\n"
                "3) Treat preprints/reviews appropriately:\n"
                "   - Review/overview can be MED if it clearly synthesizes evidence and states limitations.\n"
                "   - Preprint with weak methods detail => LOW.\n"
                "4) You MUST assign `grade_score` in [0,1] consistent with `grade_level`:\n"
                "   - HIGH: 0.75~1.00 (clear experimental/field evidence, methods + validation visible)\n"
                "   - MED:  0.50~0.74 (some empirical basis, but limitations/gaps; or strong review)\n"
                "   - LOW:  0.00~0.49 (conceptual/modeling-only, dataset-only, vague, or methods/results not evidenced)\n"
                "5) Provide `evidence_excerpt` per item: quote/paraphrase from abstract or pdf snippet showing why you graded it.\n"
                "6) `reason` must be concrete and mention what evidence is present/missing (methods, validation, scale, uncertainty).\n"
                "7) Return JSON only with this exact structure:\n"
                "- overall_grade: \"HIGH\" | \"MED\" | \"LOW\"\n"
                "- reasoning_summary: string\n"
                "- items: array of objects with fields:\n"
                "  - index (number)\n"
                "  - grade_level (\"HIGH\" | \"MED\" | \"LOW\")\n"
                "  - grade_score (number in [0,1])\n"
                "  - reason (string)\n"
                "  - evidence_excerpt (string)\n"
            ),
        ),
        ("user", "{input_block}"),
    ]
)


def _judge_chain():
    return _PROMPT | get_chat_model(temperature=0.1, json_mode=True) | JsonOutputParser()


def _claims_block(claims: list[Claim]) -> str:
    lines: list[str] = []
    for c in claims[:8]:
        lines.append(f"- 기술: {c.technology} | 타입: {c.type} | 주장: {c.claim} | 적용: {c.application} | 상태: {c.status}")
    return "\n".join(lines) if lines else "(클레임 없음)"


def _papers_block(papers: list[PaperResult]) -> str:
    chunks: list[str] = []
    for i, p in enumerate(papers):
        pdf_note = ""
        if (p.pdf_evidence or "").strip():
            pdf_note = f"    pdf_evidence_snippet:\n{p.pdf_evidence}\n"
        chunks.append(
            f"[{i}] title: {p.title}\n"
            f"    year: {p.year}\n"
            f"    abstract:\n{p.abstract}\n"
            f"    evidence_pack.summary:\n{p.summary}\n"
            f"{pdf_note}"
            f"    conditions: {p.conditions}\n"
            f"    limitations: {p.limitations}\n"
        )
    return "\n".join(chunks)


def _safe_level(v: Any) -> Literal["HIGH", "MED", "LOW"]:
    if v in ("HIGH", "MED", "LOW"):
        return v
    return "LOW"


def _safe_score(v: Any) -> float:
    try:
        x = float(v)
    except Exception:  # noqa: BLE001
        return 0.0
    if x != x:  # NaN
        return 0.0
    return max(0.0, min(1.0, x))


async def judge_papers_llm(
    papers: list[PaperResult],
    claims: list[Claim],
) -> Tuple[list[PaperResult], Literal["HIGH", "MED", "LOW"], str]:
    """
    Returns (updated_papers, overall_grade, reasoning_summary).
    If OPENAI_API_KEY is not set or parsing fails, returns inputs unchanged with overall derived from existing grades.
    """
    if not papers:
        return [], "LOW", "논문이 없어 등급을 판정할 근거가 없습니다."
    if not (settings.OPENAI_API_KEY or "").strip():
        # Keep existing heuristic grading
        overall = "LOW"
        top = papers[:3]
        if any(p.grade_level == "HIGH" for p in top):
            overall = "HIGH"
        elif any(p.grade_level == "MED" for p in top):
            overall = "MED"
        return papers, overall, "OPENAI_API_KEY 미설정으로 휴리스틱 등급을 유지했습니다."

    input_block = (
        "클레임:\n"
        f"{_claims_block(claims)}\n\n"
        "논문 후보(초록/요약 기반):\n"
        f"{_papers_block(papers[:7])}\n"
    )

    try:
        data: Any = await _judge_chain().ainvoke({"input_block": input_block})
    except Exception as exc:  # noqa: BLE001
        logger.warning("scientific grade LLM failed: %s", exc)
        return papers, "LOW", f"LLM 판정 실패로 휴리스틱을 유지했습니다: {exc!s}"

    if not isinstance(data, dict):
        return papers, "LOW", "LLM 판정 응답 형식 오류로 휴리스틱을 유지했습니다."

    overall_grade = _safe_level(data.get("overall_grade"))
    reasoning_summary = str(data.get("reasoning_summary") or "").strip()

    items = data.get("items")
    if not isinstance(items, list):
        return papers, overall_grade, reasoning_summary or "LLM 판정 결과(items)가 없어 휴리스틱을 유지했습니다."

    by_idx: dict[int, dict[str, Any]] = {}
    for it in items:
        if not isinstance(it, dict):
            continue
        try:
            idx = int(it.get("index", -1))
        except Exception:  # noqa: BLE001
            continue
        if 0 <= idx < len(papers):
            by_idx[idx] = it

    out: list[PaperResult] = []
    for i, p in enumerate(papers):
        it = by_idx.get(i)
        if not it:
            out.append(p)
            continue
        lvl = _safe_level(it.get("grade_level"))
        score = _safe_score(it.get("grade_score"))
        reason = str(it.get("reason") or "").strip()
        ev = str(it.get("evidence_excerpt") or "").strip()
        # Keep evidence-pack narrative fields; overwrite grading + ensure reason/excerpt are populated.
        out.append(
            p.model_copy(
                update={
                    "grade_level": lvl,
                    "grade_score": score,
                    "reason": reason or p.reason,
                    "excerpt": ev or p.excerpt,
                }
            )
        )

    return out, overall_grade, reasoning_summary

