from __future__ import annotations

from datetime import datetime
import logging
from pathlib import Path

from app.core.config import settings


logger = logging.getLogger(__name__)

_HTML_STYLE = """
<style>
  @page {
    size: A4;
    margin: 2cm;
  }
  body {
    font-family: "NanumGothic", "Nanum Gothic", sans-serif;
    font-size: 11pt;
    line-height: 1.6;
    color: #111;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    margin: 12px 0;
  }
  th, td {
    border: 1px solid #d0d0d0;
    padding: 4px;
    vertical-align: top;
  }
  code, pre {
    font-family: "SFMono-Regular", Consolas, monospace;
  }
  .footnotes {
    font-size: 9pt;
    border-top: 1px solid #cfcfcf;
    margin-top: 24px;
    padding-top: 8px;
  }
</style>
"""


def _resolve_output_dir() -> Path:
    output_dir = Path(settings.REPORT_OUTPUT_DIR)
    if output_dir.is_absolute():
        resolved = output_dir
    else:
        backend_root = Path(__file__).resolve().parents[3]
        resolved = backend_root / output_dir
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _build_base_name() -> str:
    return f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def _write_markdown_fallback(markdown_text: str, output_dir: Path) -> str | None:
    try:
        path = output_dir / f'{_build_base_name()}.md'
        path.write_text(markdown_text, encoding='utf-8')
        return str(path)
    except Exception:
        logger.exception('Failed to save markdown fallback report')
        return None


def export_pdf(markdown_text: str) -> str | None:
    output_dir = _resolve_output_dir()

    try:
        import markdown as markdown_lib
    except Exception:
        logger.exception('markdown package import failed; saving markdown fallback instead')
        return _write_markdown_fallback(markdown_text, output_dir)

    try:
        from weasyprint import HTML
    except Exception:
        logger.exception('weasyprint import failed; saving markdown fallback instead')
        return _write_markdown_fallback(markdown_text, output_dir)

    try:
        html_body = markdown_lib.markdown(
            markdown_text,
            extensions=['tables', 'fenced_code', 'nl2br'],
        )
        html = f'<!DOCTYPE html><html><head><meta charset="utf-8">{_HTML_STYLE}</head><body>{html_body}</body></html>'
        path = output_dir / f'{_build_base_name()}.pdf'
        HTML(string=html).write_pdf(str(path))
        return str(path)
    except Exception:
        logger.exception('PDF export failed; saving markdown fallback instead')
        return _write_markdown_fallback(markdown_text, output_dir)
