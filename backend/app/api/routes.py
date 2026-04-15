from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from app.pipeline.orchestrator import run_verification
from app.preprocessing.pdf_extract import extract_text_from_pdf_bytes
from app.schemas.api import VerificationRequest, VerificationResponse
from app.schemas.report import ChartData


router = APIRouter()

_MAX_PDF_BYTES = 15 * 1024 * 1024


@router.post('/verify', response_model=VerificationResponse)
async def verify(request: VerificationRequest):
    return await run_verification(request)


@router.post('/verify/upload', response_model=VerificationResponse)
async def verify_upload(
    content: str = Form(''),
    pdf: Optional[UploadFile] = File(None),
):
    """
    텍스트와(선택) PDF를 함께 받아 본문을 합친 뒤 기존 `/verify` 파이프라인과 동일하게 검증합니다.
    PDF는 로컬에서 텍스트만 추출합니다(저장하지 않음).
    """
    parts: list[str] = []
    c = (content or '').strip()
    if c:
        parts.append(c)

    if pdf is not None and (pdf.filename or '').strip():
        raw = await pdf.read()
        if len(raw) > _MAX_PDF_BYTES:
            raise HTTPException(status_code=400, detail='PDF 파일이 너무 큽니다(최대 15MB).')
        try:
            pdf_text = extract_text_from_pdf_bytes(raw)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=f'PDF 텍스트 추출 실패: {exc!s}') from exc
        if pdf_text.strip():
            parts.append('--- PDF에서 추출한 본문 ---\n' + pdf_text.strip())

    merged = '\n\n'.join(parts).strip()
    if len(merged) < 5:
        raise HTTPException(
            status_code=400,
            detail='검증할 내용이 없습니다. 텍스트를 입력하거나 PDF를 업로드하세요.',
        )

    request = VerificationRequest(input_type='text', content=merged)
    return await run_verification(request)


class ReportPdfRequest(BaseModel):
    markdown: str = Field(..., min_length=1)
    title: str = Field(default='기술 검증 보고서')
    chart_data: Optional[ChartData] = None


@router.post('/report/pdf')
async def download_report_pdf(body: ReportPdfRequest):
    """생성된 Markdown 보고서를 PDF로 내려받습니다(WeasyPrint 등이 설치된 환경에서만 PDF)."""
    from app.agents.report.pdf_export import export_pdf  # lazy

    path = export_pdf(body.markdown, chart_data=body.chart_data, title=body.title or '기술 검증 보고서')
    if path.lower().endswith('.pdf'):
        return FileResponse(
            path,
            media_type='application/pdf',
            filename='verification_report.pdf',
        )
    # Markdown만 저장된 경우: 클라이언트가 MD 다운로드 fallback 사용
    raise HTTPException(
        status_code=503,
        detail='PDF 엔진을 사용할 수 없습니다(서버에 weasyprint 등이 필요합니다). Markdown으로 저장된 경로만 있습니다.',
    )


@router.post('/report/markdown')
async def download_report_markdown(body: ReportPdfRequest):
    """보고서 Markdown 파일로 다운로드(항상 동작)."""
    md = body.markdown
    return Response(
        content=md,
        media_type='text/markdown; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename="verification_report.md"'},
    )
