"""
로컬 스모크: run_verification 한 번 실행 후 마크다운 요약을 stdout 또는 파일로 출력.

사용:
  cd backend && PYTHONPATH=. python scripts/smoke_verify_report.py [out.md]

상위 디렉터리의 `.env`와 `backend/.env`를 순서대로 로드합니다.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv


def _load_env() -> None:
    here = Path(__file__).resolve()
    backend = here.parents[1]
    root = backend.parent
    load_dotenv(root / ".env")
    load_dotenv(backend / ".env")


async def _main() -> str:
    _load_env()

    from app.pipeline.orchestrator import run_verification
    from app.schemas.api import VerificationRequest

    req = VerificationRequest(
        input_type="text",
        content=(
            "DAC 직접공기포집 기술로 연 1만 톤 규모 시범을 검토 중이다. "
            "국내 탄소중립기본법·EU CBAM과의 정합성, IRA 45Q 수혜 가능성을 알고 싶다."
        ),
    )
    result = await run_verification(req)

    lines: list[str] = []
    lines.append("# 에이전트 스모크 테스트 결과")
    lines.append("")
    lines.append(f"- 실행 시각(UTC): {datetime.now(timezone.utc).isoformat()}")
    lines.append("- 파이프라인: `run_verification` → LangGraph (`verification_graph.py`)")
    lines.append("")
    lines.append("## 1. 생성된 보고서 (report_markdown)")
    lines.append("")
    lines.append(result.report_markdown or "_(비어 있음)_")
    lines.append("")
    lines.append("## 2. Scientific 에이전트 요약")
    sci = result.scientific
    lines.append("")
    lines.append(f"- **overall_grade:** {sci.overall_grade}")
    lines.append(f"- **trl_estimate:** {sci.trl_estimate}")
    lines.append(f"- **search_sources:** {sci.search_sources}")
    lines.append(f"- **논문 수:** {len(sci.papers)}")
    lines.append(f"- **error:** {sci.error or '(없음)'}")
    if sci.grade_breakdown:
        gb = sci.grade_breakdown
        lines.append(f"- **grade_breakdown.weighted_total:** {gb.weighted_total}")
    lines.append("")
    lines.append("### 툴·데이터 소스 동작 (Scientific)")
    lines.append("")
    lines.append(
        "1. **Semantic Scholar** — `graph/v1/paper/search` (선택 헤더 `x-api-key`).\n"
        "2. **OpenAlex** — `works` 검색, User-Agent에 `OPENALEX_CONTACT_EMAIL` 권장.\n"
        "3. **arXiv** — `export.arxiv.org/api/query` Atom 파싱, API 키 없음.\n"
        "4. 결과는 제목 정규화로 병합 후 `grade_evaluator` 휴리스틱으로 점수화."
    )
    lines.append("")
    if sci.papers[:3]:
        lines.append("상위 논문 예시(최대 3건):")
        for i, p in enumerate(sci.papers[:3], 1):
            lines.append(f"{i}. {p.title[:120]}… — citations={p.citation_count}, grade={p.grade_level}")
    lines.append("")
    lines.append("## 3. Regulatory 에이전트 요약")
    reg = result.regulatory
    lines.append("")
    lines.append(f"- **verdict:** {reg.verdict}")
    lines.append(f"- **confidence:** {reg.confidence}")
    lines.append(f"- **source_urls (개수):** {len(reg.source_urls)}")
    lines.append(f"- **error:** {reg.error or '(없음)'}")
    if reg.pipeline_notes:
        lines.append("- **pipeline_notes:**")
        for n in reg.pipeline_notes[:12]:
            lines.append(f"  - {n}")
    lines.append("")
    lines.append("### 툴·데이터 소스 동작 (Regulatory)")
    lines.append("")
    lines.append(
        "1. **Tavily** — 규제·정책 도메인 검색 (`TAVILY_API_KEY`).\n"
        "2. **LangChain** — 법령명 추출·적용성 해석에 `ChatOpenAI` + JSON (`law_extract.py`, `regulatory_llm.py`).\n"
        "3. **국내 law.go.kr** — `LAW_GO_KR_API_KEY` 및 MST 있을 때 `lawService.do` 상세.\n"
        "4. **EU** — 스니펫/이름에서 CELEX 추정 후 EUR-Lex HTML (`eurlex.py`), 실패 시 Tavily 스니펫."
    )
    lines.append("")
    lines.append("## 4. Industrial / Cross-validation (참고)")
    lines.append("")
    ind = result.industrial
    lines.append(f"- industrial.error: {ind.error or '(없음)'}")
    lines.append(f"- cross_validation.overall_verdict: {result.cross_validation.overall_verdict}")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    out = asyncio.run(_main())
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(out, encoding="utf-8")
        print(f"Wrote {path}", file=sys.stderr)
    print(out)
