"""테스트 수집 전에 저장소 루트·backend의 .env를 로드해 OPENAI_API_KEY 등을 반영."""

from pathlib import Path

from dotenv import load_dotenv

_here = Path(__file__).resolve()
_backend = _here.parents[1]
_repo = _backend.parent
load_dotenv(_repo / ".env")
load_dotenv(_backend / ".env")
