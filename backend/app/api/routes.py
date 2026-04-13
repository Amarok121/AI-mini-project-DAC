from fastapi import APIRouter
from app.pipeline.orchestrator import run_verification
from app.schemas.api import VerificationRequest, VerificationResponse


router = APIRouter()


@router.post('/verify', response_model=VerificationResponse)
async def verify(request: VerificationRequest):
    return await run_verification(request)
