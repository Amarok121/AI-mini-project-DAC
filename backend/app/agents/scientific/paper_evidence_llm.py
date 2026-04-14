"""선정 논문에 evidence pack 필드(요약·발췌·조건·한계)를 채움 — 초록 중심, 결론은 초록에 명시된 경우에 한함."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate

from app.core.config import settings
from app.schemas.claim import Claim
from app.schemas.agent_result import PaperResult

from app.agents.langchain_setup import get_chat_model

logger = logging.getLogger(__name__)

EVIDENCE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (
                "You write structured evidence packs for downstream cross-validation (Korean). "
                "Each paper has only title, abstract, metadata — full PDF is not available. "
                "Write 3–6 sentences in `summary`: research aim, methods/setting, main findings, "
                "and limitations. If the abstract implies a conclusion, include it; otherwise state that "
                "the abstract does not explicitly state a separate conclusion section. "
                "Do not invent numbers or claims absent from the abstract. "
                "Return JSON only: {{\"items\": [{{\"index\": 0, \"summary\": \"...\", \"excerpt\": \"...\", "
                "\"key_point\": \"...\", \"conditions\": [], \"limitations\": [], \"evidence_note\": \"...\"}}]}}. "
                "`excerpt` is one short quote or tight paraphrase from the abstract. "
                "`evidence_note` is optional: how a journalist might overstate vs this evidence."
            ),
        ),
        ("user", "클레임 맥락:\n{claims_block}\n\n논문 목록:\n{papers_block}"),
    ]
)


def _evidence_chain():
    return EVIDENCE_PROMPT | get_chat_model(temperature=0.2, json_mode=True) | JsonOutputParser()


def _claims_block(claims: list[Claim]) -> str:
    lines = [f"- {c.technology} | {c.claim} | {c.application}" for c in claims[:12]]
    return "\n".join(lines) if lines else "(없음)"


def _papers_block(papers: list[PaperResult]) -> str:
    chunks: list[str] = []
    for i, p in enumerate(papers):
        chunks.append(
            f"[{i}] title: {p.title}\n"
            f"    year: {p.year} | journal: {p.journal}\n"
            f"    abstract:\n{p.abstract}\n"
        )
    return "\n".join(chunks)


def _fallback_pack(p: PaperResult) -> PaperResult:
    ab = (p.abstract or "").strip()
    if len(ab) > 80:
        summary = (
            f"초록 기준으로, 본 연구는 다음 내용을 다룬다: {ab[:900]}"
            + ("…" if len(ab) > 900 else "")
        )
        excerpt = ab[:400] + ("…" if len(ab) > 400 else "")
    else:
        summary = f"초록이 짧거나 없어 메타데이터 위주로만 정리했다. 제목: {p.title}"
        excerpt = p.title
    return p.model_copy(
        update={
            "summary": summary,
            "excerpt": excerpt,
            "key_point": "초록·메타데이터 기반 자동 요약",
            "conditions": [],
            "limitations": ["전문 미확인", "초록만으로 실험 조건이 불명확할 수 있음"] if not ab else ["전문 미확인"],
            "evidence_note": "",
        }
    )


async def enrich_papers_evidence_pack(
    papers: list[PaperResult],
    claims: list[Claim],
) -> list[PaperResult]:
    if not papers:
        return []
    if not (settings.OPENAI_API_KEY or "").strip():
        return [_fallback_pack(p) for p in papers]

    try:
        data: Any = await _evidence_chain().ainvoke(
            {
                "claims_block": _claims_block(claims),
                "papers_block": _papers_block(papers),
            }
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("paper evidence LLM failed: %s", exc)
        return [_fallback_pack(p) for p in papers]

    if not isinstance(data, dict):
        return [_fallback_pack(p) for p in papers]

    items = data.get("items")
    if not isinstance(items, list):
        return [_fallback_pack(p) for p in papers]

    by_idx: dict[int, dict[str, Any]] = {}
    for it in items:
        if not isinstance(it, dict):
            continue
        try:
            idx = int(it.get("index", -1))
        except (TypeError, ValueError):
            continue
        if 0 <= idx < len(papers):
            by_idx[idx] = it

    out: list[PaperResult] = []
    for i, p in enumerate(papers):
        it = by_idx.get(i)
        if not it:
            out.append(_fallback_pack(p))
            continue

        def _sl(key: str, default: str = "") -> str:
            v = it.get(key)
            return str(v).strip() if v is not None else default

        def _lst(key: str) -> list[str]:
            v = it.get(key)
            if not isinstance(v, list):
                return []
            return [str(x).strip() for x in v if str(x).strip()][:24]

        out.append(
            p.model_copy(
                update={
                    "summary": _sl("summary") or _fallback_pack(p).summary,
                    "excerpt": _sl("excerpt") or p.title,
                    "key_point": _sl("key_point"),
                    "conditions": _lst("conditions"),
                    "limitations": _lst("limitations"),
                    "evidence_note": _sl("evidence_note"),
                }
            )
        )

    return out
