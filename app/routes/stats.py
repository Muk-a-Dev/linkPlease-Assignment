from fastapi import APIRouter
from app.db import get_stats
from app.schemas import StatsResponse

router = APIRouter()


@router.get("/stats", response_model=StatsResponse)
async def read_stats():
    stats_data = await get_stats()
    return StatsResponse(**stats_data)
