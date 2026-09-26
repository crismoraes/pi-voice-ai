"""Read-only API for the local token usage dashboard."""

import asyncio

from fastapi import APIRouter, Query

from app.usage.runtime import usage_store

router = APIRouter(prefix="/api/usage", tags=["usage"])


@router.get("/summary")
async def usage_summary(days: int = Query(default=30, ge=1, le=3650)) -> dict[str, object]:
    return await asyncio.to_thread(usage_store.summary, days)


@router.get("/turns")
async def usage_turns(
    days: int = Query(default=30, ge=1, le=3650),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, object]:
    turns = await asyncio.to_thread(usage_store.recent, days, limit)
    return {"days": days, "turns": turns}
