import logging
from fastapi import APIRouter

router = APIRouter(prefix="/admin", tags=["admin"])
logger = logging.getLogger(__name__)

@router.post("/trigger-computed-metrics")
async def trigger_computed_metrics():
    from backend.app.services.computed_metrics import run_daily_computed_metrics
    await run_daily_computed_metrics()
    return {"status": "done"}
