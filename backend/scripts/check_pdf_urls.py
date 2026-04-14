"""
PDF URL이 HTTP로 받을 수 있는지 확인합니다 (HEAD 후 필요 시 소량 GET).

사용 예:
  cd backend && PYTHONPATH=. python scripts/check_pdf_urls.py \\
    "https://arxiv.org/pdf/1706.03762.pdf"

여러 개:
  python scripts/check_pdf_urls.py --url URL1 --url URL2

`verify` 응답의 `cross_validation.papers_for_validation[].pdf_url` 등을 붙여 넣어 테스트할 수 있습니다.
"""

from __future__ import annotations

import argparse
import sys

import httpx


def _is_pdf_magic(chunk: bytes) -> bool:
    return len(chunk) >= 4 and chunk[:4] == b"%PDF"


def check_pdf_url(url: str, *, timeout: float = 25.0) -> tuple[bool, str]:
    u = (url or "").strip()
    if not u:
        return False, "empty url"
    headers = {"User-Agent": "AI-mini-project-DAC-pdf-check/1.0"}

    with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
        try:
            h = client.head(u)
        except httpx.HTTPError as e:
            return False, f"HEAD error: {e!s}"

        ct_h = (h.headers.get("content-type") or "").lower()
        if h.status_code < 400 and "pdf" in ct_h:
            return True, f"HEAD {h.status_code} content-type={ct_h.split(';')[0].strip()}"

        try:
            g = client.get(u, headers={"Range": "bytes=0-8191"})
        except httpx.HTTPError as e:
            return False, f"GET error: {e!s}"

        ct = (g.headers.get("content-type") or "").lower()
        chunk = g.content[:4096] if g.content else b""

        if g.status_code >= 400:
            return False, f"GET HTTP {g.status_code}"

        if "pdf" in ct:
            return True, f"GET {g.status_code} content-type={ct.split(';')[0].strip()}"

        if _is_pdf_magic(chunk):
            return True, f"GET {g.status_code} body signature %PDF ({len(chunk)} B sampled)"

        return (
            False,
            f"GET {g.status_code} — not recognized as PDF (content-type={ct.split(';')[0]!s}, sample={chunk[:24]!r})",
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Check PDF URLs are retrievable")
    parser.add_argument("urls", nargs="*", help="PDF URLs")
    parser.add_argument("--url", action="append", dest="urls_opt", help="URL (repeatable)")
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Include known arXiv PDF if no URLs given",
    )
    args = parser.parse_args()

    urls: list[str] = [u for u in args.urls if u]
    if args.urls_opt:
        urls.extend(args.urls_opt)
    if args.sample or not urls:
        urls.append("https://arxiv.org/pdf/1706.03762.pdf")

    any_fail = False
    for u in urls:
        ok, msg = check_pdf_url(u)
        label = "OK " if ok else "BAD"
        print(f"[{label}] {u}\n      {msg}")
        if not ok:
            any_fail = True

    return 1 if any_fail else 0


if __name__ == "__main__":
    sys.exit(main())
