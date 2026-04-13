from pathlib import Path
from app.core.config import settings


def _company_dir(company_name: str) -> Path:
    return Path(settings.DART_DOCS_DIR) / company_name


async def fetch_company_documents(company_name: str) -> list[dict]:
    """
    로컬에 미리 다운로드된 DART 문서를 읽습니다.
    기대 구조:
    data/dart/{company_name}/*.pdf
    """
    base = _company_dir(company_name)
    if not base.exists():
        return []

    docs: list[dict] = []
    for path in sorted(base.glob('*')):
        if path.suffix.lower() != '.pdf':
            continue
        docs.append(
            {
                'file_name': path.name,
                'content': _extract_pdf_text(path),
                'metadata': {'source': 'local_dart_dump'},
            }
        )
    return docs


def list_companies_with_local_docs() -> list[str]:
    root = Path(settings.DART_DOCS_DIR)
    if not root.exists():
        return []
    return sorted([p.name for p in root.iterdir() if p.is_dir()])


def _extract_pdf_text(path: Path) -> str:
    # TODO: pypdf/pdfplumber 연동으로 실제 PDF 텍스트 추출 구현
    return f'[PDF 파싱 TODO] {path.name}'
