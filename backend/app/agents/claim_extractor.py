"""클레임 추출: 정제된 본문에서 검증 가능한 기술 주장을 구조화 (LangChain + OpenAI JSON)."""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import ValidationError

from app.core.config import settings
from app.schemas.claim import Claim

from app.agents.langchain_setup import get_chat_model

logger = logging.getLogger(__name__)

_MAX_INPUT_CHARS = 14_000
_MAX_CLAIMS = 10
_MIN_CLAIM_CHARS = 10
_DEDUPE_CLAIM_PREFIX = 96

# 허용 type 라벨 (그 외는 "일반"으로 통일)
_ALLOWED_TYPES = frozenset(
    {
        "성능 지표",
        "경제성",
        "규제",
        "안전성",
        "일반",
        "환경",
        "사업성",
        "기술성",
        "일정",
        "규모",
    }
)

# few-shot + 지시문 (JSON 중괄호는 LangChain 이스케이프: {{ }} )
CLAIM_EXTRACT_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (
                "You extract distinct, checkable technology claims from the user's text (Korean and/or English). "
                "Each claim must be verifiable in principle (performance, economics, regulation, safety, schedule). "
                "Return JSON only with this shape:\n"
                '{{"claims": [{{"technology": "...", "claim": "...", "application": "...", "type": "...", "status": "달성"|"목표"}}]}}\n'
                "Rules:\n"
                '- "technology": short noun phrase (e.g. DAC, 전해조).\n'
                '- "claim": one factual sentence grounded in the text; do not add numbers or citations absent from the text.\n'
                '- "application": context (site, sector); use "" if unknown.\n'
                '- "type": one of: 성능 지표, 경제성, 규제, 안전성, 일반, 환경, 사업성, 기술성, 일정, 규모.\n'
                '- "status": "달성" if stated as achieved / completed fact; "목표" for plans, targets, or future intent.\n'
                "If the text is vague, return a single broad claim. Max 10 claims.\n"
                "\n"
                "Examples (structure only):\n"
                '{{"claims": [{{"technology": "DAC", "claim": "2027년까지 연 1만 톤 규모 시범 가동을 검토 중이다", "application": "국내 공장", "type": "규모", "status": "목표"}}]}}\n'
                '{{"claims": [{{"technology": "CO2 캡처", "claim": "The unit completed 1000 hours of continuous operation in the lab", "application": "", "type": "성능 지표", "status": "달성"}}]}}\n'
            ),
        ),
        ("user", "본문:\n\n{text}"),
    ]
)


def _claim_extract_chain():
    return CLAIM_EXTRACT_PROMPT | get_chat_model(temperature=0.15, json_mode=True) | JsonOutputParser()


def _normalize_status(v: Any) -> str:
    s = str(v or "").strip()
    if s in ("달성", "목표"):
        return s
    low = s.lower()
    if low in ("achieved", "done", "completed", "fact"):
        return "달성"
    if low in ("goal", "target", "planned", "plan", "considering", "reviewing"):
        return "목표"
    return "목표"


def _sanitize_type(v: Any) -> str:
    s = str(v or "").strip()[:100]
    if s in _ALLOWED_TYPES:
        return s
    return "일반"


def _claim_sig(c: Claim) -> str:
    blob = (c.technology + "|" + c.claim[:_DEDUPE_CLAIM_PREFIX]).lower()
    return re.sub(r"[^a-z0-9가-힣]+", "", blob)[:200]


def _tokens(s: str) -> set[str]:
    return {t for t in re.findall(r"[\w가-힣]{2,}", s.lower()) if len(t) > 1}


def _grounding_ok(claim_text: str, source: str) -> bool:
    """본문과 단어 겹침이 너무 적으면 환각 가능성으로 제외 (완화된 휴리스틱)."""
    ct = _tokens(claim_text)
    st = _tokens(source)
    if not ct:
        return False
    overlap = ct & st
    n = len(ct)
    if n <= 3:
        return len(overlap) >= 1
    if len(overlap) >= max(2, int(n * 0.25)):
        return True
    return len(overlap) >= 3


def _claim_from_dict(d: dict[str, Any]) -> Optional[Claim]:
    try:
        tech = str(d.get("technology") or "").strip() or "(미상)"
        cl = str(d.get("claim") or "").strip()
        if len(cl) < _MIN_CLAIM_CHARS:
            return None
        return Claim(
            technology=tech[:500],
            claim=cl[:2000],
            application=str(d.get("application") or "").strip()[:1000],
            type=_sanitize_type(d.get("type")),
            status=_normalize_status(d.get("status")),  # type: ignore[arg-type]
        )
    except ValidationError:
        return None
    except Exception:  # noqa: BLE001
        return None


def _dedupe(claims: list[Claim]) -> list[Claim]:
    seen: set[str] = set()
    out: list[Claim] = []
    for c in claims:
        sig = _claim_sig(c)
        if not sig or sig in seen:
            continue
        seen.add(sig)
        out.append(c)
    return out


def _post_validate_claims(claims: list[Claim], source_text: str) -> list[Claim]:
    """중복 제거·최소 길이·본문 근거 휴리스틱."""
    src = source_text[:_MAX_INPUT_CHARS]
    filtered: list[Claim] = []
    for c in claims:
        if len(c.claim.strip()) < _MIN_CLAIM_CHARS:
            continue
        if not _grounding_ok(c.claim, src):
            logger.debug("claim_extractor: grounding drop: %s", c.claim[:80])
            continue
        filtered.append(c)
    filtered = _dedupe(filtered)
    return filtered[:_MAX_CLAIMS]


def _fallback_claims_from_text(text: str) -> list[Claim]:
    """API 키 없음·파싱 실패 시 최소 1건으로 파이프라인 유지."""
    t = re.sub(r"\s+", " ", (text or "").strip())
    if not t:
        return []
    snippet = t[:800] + ("…" if len(t) > 800 else "")
    if len(snippet) < _MIN_CLAIM_CHARS:
        snippet = (snippet + " — 본문이 짧아 요약만 표시합니다.")[:2000]
    return [
        Claim(
            technology="(자동 요약)",
            claim=snippet,
            application="",
            type="일반",
            status="목표",
        )
    ]


async def run_claim_extractor(text: str) -> list[Claim]:
    raw = (text or "").strip()
    if not raw:
        return []

    if not (settings.OPENAI_API_KEY or "").strip():
        logger.info("claim_extractor: OPENAI_API_KEY 없음 — 폴백 클레임 사용")
        return _fallback_claims_from_text(raw)

    truncated = raw[:_MAX_INPUT_CHARS]
    if len(raw) > _MAX_INPUT_CHARS:
        truncated += "\n\n[…본문이 길어 앞부분만 사용했습니다.]"

    try:
        data: Any = await _claim_extract_chain().ainvoke({"text": truncated})
    except Exception as exc:  # noqa: BLE001
        logger.warning("claim_extractor chain failed: %s", exc)
        return _fallback_claims_from_text(raw)

    if not isinstance(data, dict):
        return _fallback_claims_from_text(raw)

    raw_list = data.get("claims")
    if not isinstance(raw_list, list):
        return _fallback_claims_from_text(raw)

    out: list[Claim] = []
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        c = _claim_from_dict(item)
        if c:
            out.append(c)
        if len(out) >= _MAX_CLAIMS * 2:
            break

    out = _post_validate_claims(out, raw)

    if not out:
        logger.info("claim_extractor: 모델 출력이 검증에서 제거됨 — 폴백")
        return _fallback_claims_from_text(raw)

    return out
