"""
Dump actual JSON outputs for downstream inspection.

Usage:
  cd backend && PYTHONPATH=. python scripts/dump_agent_outputs.py [out_dir]

Writes:
  - verification_response.json
  - scientific_agent_output.json
  - regulatory_agent_output.json

This script loads environment variables from the repo root `.env` and `backend/.env`
in that order (same as `smoke_verify_report.py`).
"""

from __future__ import annotations

import asyncio
import json
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


def _write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


async def _main(out_dir: Path) -> None:
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

    meta = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "request": req.model_dump(),
    }

    _write_json(out_dir / "verification_response.json", {"meta": meta, "data": result.model_dump()})
    _write_json(out_dir / "scientific_agent_output.json", {"meta": meta, "data": result.scientific.model_dump()})
    _write_json(out_dir / "regulatory_agent_output.json", {"meta": meta, "data": result.regulatory.model_dump()})


if __name__ == "__main__":
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/_agent_outputs_latest")
    asyncio.run(_main(out_dir))
