"""Health endpoint independent of external services."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Report whether the HTTP process is available."""
    return {"status": "ok"}
