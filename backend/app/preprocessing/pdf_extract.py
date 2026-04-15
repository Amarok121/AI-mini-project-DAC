"""PDF에서 평문 추출(클레임 추출 파이프라인 입력용)."""

from __future__ import annotations

import io

from pypdf import PdfReader


def extract_text_from_pdf_bytes(data: bytes, *, max_pages: int = 40, max_chars: int = 120_000) -> str:
    if not data:
        return ""
    reader = PdfReader(io.BytesIO(data))
    chunks: list[str] = []
    for i, page in enumerate(reader.pages[:max_pages]):
        try:
            t = page.extract_text() or ""
        except Exception:  # noqa: BLE001
            t = ""
        if t.strip():
            chunks.append(t)
    text = "\n\n".join(chunks).strip()
    if len(text) > max_chars:
        return text[:max_chars] + "…"
    return text
