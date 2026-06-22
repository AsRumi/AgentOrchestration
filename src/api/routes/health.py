from fastapi import APIRouter
from src.api.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["System"])
def health_check():
    """Check that the API is running."""
    return HealthResponse(status="ok")
