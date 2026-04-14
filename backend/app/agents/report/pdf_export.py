from __future__ import annotations

from datetime import datetime
import logging
from pathlib import Path
import re

from app.core.config import settings


logger = logging.getLogger(__name__)

_HTML_STYLE = """
<style>
  @page {
    size: A4;
    margin: 2cm;
    @top-center {
      content: string(report-title);
      font-size: 9pt;
      color: #6c757d;
    }
    @bottom-center {
      content: counter(page);
      font-size: 9pt;
      color: #6c757d;
    }
  }
  @page :first {
    @top-center {
      content: "";
    }
    @bottom-center {
      content: "";
    }
  }
  body {
    font-family: "Malgun Gothic", "Apple SD Gothic Neo", "Noto Sans KR", "NanumGothic", "Nanum Gothic", sans-serif;
    font-size: 9pt;
    line-height: 1.45;
    color: #111;
  }
  h1 {
    string-set: report-title content();
    font-size: 20pt;
  }
  h2 {
    color: #1f2d3d;
    margin-top: 18px;
    font-size: 14pt;
  }
  h3 {
    color: #2c3e50;
    border-bottom: 1px solid #dee2e6;
    padding-bottom: 6px;
    margin-top: 24px;
    font-size: 11pt;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    margin: 12px 0;
  }
  th, td {
    border: 1px solid #d0d0d0;
    padding: 6px;
    vertical-align: top;
  }
  th {
    background: #f0f4f8;
  }
  .section-block {
    border-top: 1px solid #dee2e6;
    padding-top: 12px;
    margin-top: 18px;
  }
  code, pre {
    font-family: "SFMono-Regular", Consolas, monospace;
  }
  sup {
    vertical-align: super;
    font-size: 0.75em;
  }
  .footnotes {
    font-size: 9pt;
    border-top: 1px solid #cfcfcf;
    margin-top: 24px;
    padding-top: 8px;
  }
  .cover-page {
    text-align: center;
    padding-top: 120px;
    page-break-after: always;
  }
  .cover-title {
    font-size: 22pt;
    font-weight: 700;
    margin-bottom: 12px;
  }
  .cover-subtitle {
    font-size: 11pt;
    color: #4b5563;
    margin-bottom: 28px;
  }
  .cover-divider {
    width: 140px;
    height: 2px;
    background: #2c3e50;
    margin: 0 auto 28px auto;
  }
  .cover-meta {
    font-size: 10pt;
    margin: 8px 0;
  }
  .cover-note {
    margin-top: 180px;
    font-size: 8pt;
    color: #6c757d;
  }
  .toc-page {
    page-break-after: always;
  }
  .toc-title {
    font-size: 15pt;
    margin-bottom: 16px;
    color: #1f2d3d;
  }
  .toc-list {
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .toc-item {
    display: table;
    width: 100%;
    border-bottom: 1px dotted #cbd5e1;
    padding: 8px 0;
    color: #334155;
    font-size: 9pt;
  }
  .toc-item-text,
  .toc-item-no {
    display: table-cell;
    vertical-align: middle;
  }
  .toc-item-no {
    width: 34px;
    font-weight: 700;
    color: #64748b;
  }
  .score-panel {
    display: table;
    width: 100%;
    max-width: 100%;
    table-layout: fixed;
    margin: 12px 0 24px 0;
    border: 1px solid #dbe3ec;
    background: linear-gradient(180deg, #fbfcfe 0%, #f6f8fb 100%);
    page-break-inside: avoid;
    break-inside: avoid;
    box-sizing: border-box;
    overflow: hidden;
  }
  .score-panel::after {
    content: "";
    display: block;
    clear: both;
  }
  .score-panel-chart,
  .score-panel-cards {
    display: table-cell;
    vertical-align: top;
    padding: 0;
    box-sizing: border-box;
  }
  .score-panel-chart {
    width: 44%;
    border-right: 1px solid #dbe3ec;
  }
  .score-panel-cards {
    width: 56%;
  }
  .score-panel-chart-inner,
  .score-panel-cards-inner {
    padding: 14px;
    box-sizing: border-box;
    width: 100%;
  }
  .score-panel + table,
  .score-panel + p + table,
  .score-panel + div + table {
    display: table;
    width: 100%;
    margin-left: 0;
    margin-right: 0;
    table-layout: fixed;
    page-break-inside: auto;
    break-inside: auto;
    clear: both;
  }
  .panel-title {
    font-size: 9pt;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: #64748b;
    margin-bottom: 12px;
  }
  .radar-wrap {
    text-align: center;
    page-break-inside: avoid;
    break-inside: avoid;
  }
  .radar-caption {
    margin-top: 10px;
    font-size: 7.5pt;
    color: #64748b;
  }
  .score-cards {
    width: 100%;
  }
  .score-card {
    border: 1px solid #d9e2ec;
    background: #ffffff;
    padding: 14px 16px;
    margin-bottom: 12px;
  }
  .score-name {
    font-size: 8pt;
    color: #6c757d;
    margin-bottom: 6px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .score-value {
    font-size: 16pt;
    font-weight: 700;
    margin-bottom: 2px;
  }
  .score-label {
    font-size: 8.5pt;
    min-height: 18px;
    color: #2c3e50;
    margin-bottom: 10px;
    font-weight: 600;
  }
  .score-rationale {
    font-size: 7.5pt;
    color: #52606d;
    min-height: 30px;
    margin-bottom: 10px;
  }
  .score-bar {
    width: 100%;
    height: 10px;
    background: #e9ecef;
    border-radius: 999px;
    overflow: hidden;
  }
  .score-fill {
    height: 100%;
    border-radius: 999px;
  }
  .score-fill-trl { background: #3498db; }
  .score-fill-mrl { background: #2ecc71; }
  .score-fill-cri { background: #e67e22; }
  .badge-support,
  .badge-refute,
  .badge-uncertain {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 999px;
    font-size: 7.5pt;
    font-weight: 700;
  }
  .badge-support {
    background: #d4edda;
    color: #155724;
  }
  .badge-refute {
    background: #f8d7da;
    color: #721c24;
  }
  .badge-uncertain {
    background: #fff3cd;
    color: #856404;
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


def _build_cover_page(title: str) -> str:
    safe_title = title or '기술 검증 보고서'
    return f"""
    <section class="cover-page">
      <div class="cover-title">{safe_title}</div>
      <div class="cover-subtitle">기술 검증 및 도입 가능성 분석 보고서</div>
      <div class="cover-divider"></div>
      <div class="cover-meta">작성일: {datetime.now().strftime('%Y-%m-%d')}</div>
      <div class="cover-meta">회사명: SK이노베이션</div>
      <div class="cover-note">본 문서는 AI 기반 분석 결과를 정리한 참고 자료이며, 최종 의사결정 전 전문가 검토가 필요합니다.</div>
    </section>
    """


def _extract_toc_items(markdown_text: str) -> list[str]:
    lines = markdown_text.splitlines()
    items: list[str] = []
    in_toc = False
    for line in lines:
        stripped = line.strip()
        if stripped == '## 목차':
            in_toc = True
            continue
        if in_toc and stripped.startswith('### '):
            break
        if in_toc and stripped.startswith('- '):
            items.append(stripped[2:].strip())
    return items


def _build_toc_page(markdown_text: str) -> str:
    items = _extract_toc_items(markdown_text)
    if not items:
        return ''

    rows = []
    for index, item in enumerate(items, start=1):
        rows.append(
            f'<li class="toc-item"><span class="toc-item-no">{index:02d}</span><span class="toc-item-text">{item}</span></li>'
        )
    return (
        '<section class="toc-page">'
        '<div class="toc-title">목차</div>'
        f'<ol class="toc-list">{"".join(rows)}</ol>'
        '</section>'
    )


def _remove_markdown_toc_from_html(html_body: str) -> str:
    return re.sub(r'<h2>목차</h2>.*?(?=<h3>|$)', '', html_body, flags=re.S)


def _score_ratio(value: int | None, max_value: int) -> int:
    if value is None or max_value <= 0:
        return 0
    return max(0, min(100, int((value / max_value) * 100)))


def _build_radar_chart(chart_data) -> str:
    if not chart_data or not getattr(chart_data, 'score_summary', None):
        return ''

    summary = chart_data.score_summary
    points = [
        ('TRL', summary.trl, 330, '#3498db'),
        ('MRL', summary.mrl, 90, '#2ecc71'),
        ('CRI', summary.cri, 210, '#e67e22'),
    ]

    center_x = 150
    center_y = 150
    radius = 92

    def polar(value_ratio: float, degrees: float) -> tuple[float, float]:
        import math

        rad = math.radians(degrees)
        x = center_x + (radius * value_ratio) * math.cos(rad)
        y = center_y - (radius * value_ratio) * math.sin(rad)
        return (round(x, 2), round(y, 2))

    grid_levels = []
    for level in (0.25, 0.5, 0.75, 1.0):
        coords = [polar(level, deg) for _, _, deg, _ in points]
        grid_levels.append(' '.join(f'{x},{y}' for x, y in coords))

    data_coords = []
    labels = []
    for name, item, degrees, color in points:
        ratio = (item.value / item.max) if item.value is not None and item.max else 0.0
        x, y = polar(ratio, degrees)
        lx, ly = polar(1.18, degrees)
        ax, ay = polar(1.0, degrees)
        data_coords.append(f'{x},{y}')
        labels.append(
            f'<line x1="{center_x}" y1="{center_y}" x2="{ax}" y2="{ay}" stroke="#cbd5e1" stroke-width="1" />'
            f'<text x="{lx}" y="{ly}" text-anchor="middle" font-size="12" fill="{color}" font-weight="700">{name}</text>'
        )

    grid_svg = ''.join(
        f'<polygon points="{points_text}" fill="none" stroke="#dbe3ec" stroke-width="1" />'
        for points_text in grid_levels
    )
    point_circles = ''.join(
        f'<circle cx="{coord.split(",")[0]}" cy="{coord.split(",")[1]}" r="4" fill="#2c82c9" />'
        for coord in data_coords
    )
    return (
        '<div class="radar-wrap">'
        '<div class="panel-title">Score Radar</div>'
        '<svg width="260" height="260" viewBox="0 0 300 300" aria-label="score radar chart">'
        f'{grid_svg}'
        f'{"".join(labels)}'
        f'<polygon points="{" ".join(data_coords)}" fill="rgba(52, 152, 219, 0.18)" stroke="#2c82c9" stroke-width="2" />'
        f'{point_circles}'
        '</svg>'
        '<div class="radar-caption">TRL / MRL / CRI의 상대적 현재 수준을 시각적으로 비교한 요약 차트</div>'
        '</div>'
    )


def _build_score_cards(chart_data) -> str:
    if not chart_data or not getattr(chart_data, 'score_summary', None):
        return ''

    summary = chart_data.score_summary
    items = [
        ('TRL', summary.trl, 'trl'),
        ('MRL', summary.mrl, 'mrl'),
        ('CRI', summary.cri, 'cri'),
    ]

    cards = ['<div class="panel-title">KPI Summary</div><div class="score-cards">']
    for name, item, css_name in items:
        ratio = _score_ratio(item.value, item.max)
        value_text = f'{item.value}/{item.max}' if item.value is not None else f'-/{item.max}'
        cards.append(
            f"""
            <div class="score-card">
              <div class="score-name">{name}</div>
              <div class="score-value">{value_text}</div>
              <div class="score-label">{item.label}</div>
              <div class="score-rationale">{item.rationale or '판단 근거 정보 없음'}</div>
              <div class="score-bar"><div class="score-fill score-fill-{css_name}" style="width: {ratio}%;"></div></div>
            </div>
            """
        )
    cards.append('</div>')
    return ''.join(cards)


def _insert_score_cards(html_body: str, chart_data) -> str:
    radar_chart = _build_radar_chart(chart_data)
    score_cards = _build_score_cards(chart_data)
    if not radar_chart and not score_cards:
        return html_body

    score_panel = (
        '<section class="score-panel">'
        f'<div class="score-panel-chart"><div class="score-panel-chart-inner">{radar_chart}</div></div>'
        f'<div class="score-panel-cards"><div class="score-panel-cards-inner">{score_cards}</div></div>'
        '</section>'
    )
    marker = '<h3>최종 평가표 및 해설</h3>'
    if marker in html_body:
        return html_body.replace(marker, f'{marker}{score_panel}', 1)
    return score_panel + html_body


def _decorate_verdict_badges(html_body: str) -> str:
    html_body = re.sub(r'>(\s*지지\s*)<', r'><span class="badge-support">지지</span><', html_body)
    html_body = re.sub(r'>(\s*반박\s*)<', r'><span class="badge-refute">반박</span><', html_body)
    html_body = re.sub(r'>(\s*불확실\s*)<', r'><span class="badge-uncertain">불확실</span><', html_body)
    return html_body


def _decorate_sections(html_body: str) -> str:
    return re.sub(r'<h3>', '<div class="section-block"></div><h3>', html_body, count=0)


def export_pdf(markdown_text: str, chart_data=None, title: str = '') -> str | None:
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
        toc_page = _build_toc_page(markdown_text)
        html_body = _remove_markdown_toc_from_html(html_body)
        html_body = _insert_score_cards(html_body, chart_data)
        html_body = _decorate_verdict_badges(html_body)
        html_body = _decorate_sections(html_body)
        cover_page = _build_cover_page(title)
        html = (
            f'<!DOCTYPE html><html><head><meta charset="utf-8">{_HTML_STYLE}</head>'
            f'<body>{cover_page}{toc_page}{html_body}</body></html>'
        )
        path = output_dir / f'{_build_base_name()}.pdf'
        HTML(string=html).write_pdf(str(path))
        return str(path)
    except Exception:
        logger.exception('PDF export failed; saving markdown fallback instead')
        return _write_markdown_fallback(markdown_text, output_dir)
