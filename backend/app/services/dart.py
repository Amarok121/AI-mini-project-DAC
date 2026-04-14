import logging
from pathlib import Path
import re

import pdfplumber
import pymupdf4llm
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import OpenAI

from app.core.config import settings


logger = logging.getLogger(__name__)

MIN_CHUNK_LENGTH = 80
COMPANY_NAME = 'sk_innovation'
TABLE_SUMMARY_MODEL = 'gpt-4o-mini'
_TEXT_SPLITTER = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=150)
_OPENAI_CLIENT: OpenAI | None = None


def _docs_root() -> Path:
    root = Path(settings.DART_DOCS_DIR)
    if root.exists():
        return root

    backend_root = Path(__file__).resolve().parents[2]
    fallback = backend_root.parent / settings.DART_DOCS_DIR
    return fallback


def _company_dir(company_name: str) -> Path:
    return _docs_root() / company_name


def _get_openai_client() -> OpenAI | None:
    global _OPENAI_CLIENT

    if not settings.OPENAI_API_KEY:
        return None
    if _OPENAI_CLIENT is None:
        _OPENAI_CLIENT = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _OPENAI_CLIENT


def _read_pdf_as_markdown(pdf_path: Path) -> str:
    try:
        return pymupdf4llm.to_markdown(str(pdf_path))
    except Exception as exc:
        logger.warning('pymupdf4llm failed for %s, falling back to pdfplumber: %s', pdf_path, exc)
        pages: list[str] = []
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ''
                if text.strip():
                    pages.append(text)
        return '\n\n'.join(pages)


def _normalize_markdown(markdown_text: str) -> list[str]:
    normalized = markdown_text.replace('\r\n', '\n').replace('\r', '\n')
    return normalized.split('\n')


def _is_heading_line(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith('## ') or stripped.startswith('### ')


def _is_table_line(line: str) -> bool:
    return line.lstrip().startswith('|')


def _clean_text(text: str) -> str:
    text = text.strip()
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text


def _summarize_table(table_markdown: str) -> str:
    client = _get_openai_client()
    if client is None:
        logger.warning('OPENAI_API_KEY is missing. Using fallback summary for table chunk.')
        preview = table_markdown[:400].strip()
        return f'표 요약을 생성하지 못해 원문 일부를 대신 제공합니다. {preview}'

    try:
        response = client.responses.create(
            model=TABLE_SUMMARY_MODEL,
            temperature=0.0,
            input=[
                {
                    'role': 'system',
                    'content': [
                        {
                            'type': 'input_text',
                            'text': '다음 마크다운 표를 2~3문장 한국어 설명으로 요약하세요. 수치와 핵심 비교 포인트를 보존하세요.',
                        }
                    ],
                },
                {'role': 'user', 'content': [{'type': 'input_text', 'text': table_markdown}]},
            ],
        )
        summary = (response.output_text or '').strip()
        return summary or '표 요약을 생성하지 못했습니다.'
    except Exception as exc:
        logger.warning('Table summarization failed: %s', exc)
        preview = table_markdown[:400].strip()
        return f'표 요약 생성 실패. 원문 일부: {preview}'


def _build_document(content: str, source_file: str, chunk_type: str, chunk_index: int) -> Document | None:
    cleaned = _clean_text(content)
    if len(cleaned) < MIN_CHUNK_LENGTH:
        return None
    return Document(
        page_content=cleaned,
        metadata={
            'source_file': source_file,
            'chunk_type': chunk_type,
            'chunk_index': chunk_index,
            'company': COMPANY_NAME,
        },
    )


def _append_paragraph_documents(
    documents: list[Document],
    source_file: str,
    paragraph_text: str,
    chunk_index: int,
) -> int:
    text = _clean_text(paragraph_text)
    if len(text) < MIN_CHUNK_LENGTH:
        return chunk_index

    for split in _TEXT_SPLITTER.split_text(text):
        doc = _build_document(split, source_file, 'paragraph', chunk_index)
        if doc is not None:
            documents.append(doc)
            chunk_index += 1
    return chunk_index


def load_and_chunk(pdf_path: str) -> list[Document]:
    path = Path(pdf_path)
    markdown_text = _read_pdf_as_markdown(path)
    lines = _normalize_markdown(markdown_text)

    documents: list[Document] = []
    chunk_index = 0
    loose_paragraph_lines: list[str] = []
    heading_lines: list[str] = []
    in_heading = False
    current_heading_lines: list[str] = []

    def flush_heading() -> None:
        nonlocal chunk_index, current_heading_lines, in_heading
        if not current_heading_lines:
            in_heading = False
            return
        doc = _build_document('\n'.join(current_heading_lines), path.name, 'heading', chunk_index)
        if doc is not None:
            documents.append(doc)
            chunk_index += 1
        current_heading_lines = []
        in_heading = False

    def flush_loose_paragraphs() -> None:
        nonlocal chunk_index, loose_paragraph_lines
        if not loose_paragraph_lines:
            return
        chunk_index = _append_paragraph_documents(
            documents,
            path.name,
            '\n'.join(loose_paragraph_lines),
            chunk_index,
        )
        loose_paragraph_lines = []

    def flush_table(table_lines: list[str]) -> None:
        nonlocal chunk_index
        table_text = _clean_text('\n'.join(table_lines))
        if len(table_text) < MIN_CHUNK_LENGTH:
            return
        summary = _summarize_table(table_text)
        content = f'[표 설명]\n{summary}\n\n[원문]\n{table_text}'
        doc = _build_document(content, path.name, 'table', chunk_index)
        if doc is not None:
            documents.append(doc)
            chunk_index += 1

    i = 0
    while i < len(lines):
        line = lines[i]

        if _is_table_line(line):
            flush_loose_paragraphs()
            table_lines: list[str] = []
            while i < len(lines) and _is_table_line(lines[i]):
                table_lines.append(lines[i].rstrip())
                i += 1
            if in_heading:
                current_heading_lines.append('')
            flush_table(table_lines)
            continue

        if _is_heading_line(line):
            flush_loose_paragraphs()
            flush_heading()
            in_heading = True
            current_heading_lines = [line.strip()]
            i += 1
            continue

        stripped = line.strip()
        if in_heading:
            current_heading_lines.append(stripped if stripped else '')
        else:
            heading_lines.append(stripped)
            loose_paragraph_lines.append(stripped if stripped else '')
        i += 1

    flush_loose_paragraphs()
    flush_heading()
    return documents


def load_all_documents() -> list[Document]:
    root = _docs_root()
    if not root.exists():
        logger.warning('DART documents directory does not exist: %s', root)
        return []

    documents: list[Document] = []
    for pdf_path in sorted(root.rglob('*.pdf')):
        documents.extend(load_and_chunk(str(pdf_path)))
    return documents


async def fetch_company_documents(company_name: str) -> list[dict]:
    base = _company_dir(company_name)
    if not base.exists():
        return []

    docs: list[dict] = []
    for path in sorted(base.rglob('*.pdf')):
        content = _read_pdf_as_markdown(path)
        docs.append(
            {
                'file_name': path.name,
                'content': content,
                'metadata': {'source': 'local_dart_dump', 'company': company_name},
            }
        )
    return docs


def list_companies_with_local_docs() -> list[str]:
    root = _docs_root()
    if not root.exists():
        return []
    return sorted([p.name for p in root.iterdir() if p.is_dir()])
