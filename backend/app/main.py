from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from backend.app.api.v1 import me, quickbooks, stripe, slack
from backend.app.services.proactive_alerts import run_proactive_alerts
from backend.app.services.monthly_report import run_monthly_reports
from backend.app.services.sync import run_daily_qbo_sync
from backend.app.services.computed_metrics import run_daily_computed_metrics
from backend.app.logging_config import setup_logging
from backend.app.middleware import CorrelationIDMiddleware, SecurityHeadersMiddleware
from backend.app.config import get_settings

scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup: Initialize logging first, then scheduler
    setup_logging()
    scheduler.add_job(run_daily_qbo_sync, 'cron', hour=2, minute=0)
    scheduler.add_job(run_daily_computed_metrics, 'cron', hour=3, minute=0)
    scheduler.add_job(run_proactive_alerts, 'cron', hour=9, minute=0)
    scheduler.add_job(run_monthly_reports, 'cron', day=1, hour=9, minute=0)
    scheduler.start()
    yield
    # Shutdown: cleanup goes here
    scheduler.shutdown()


app = FastAPI(
    title="Flowytics API",
    description="Agentic CFO — AI-powered managerial accounting for startups",
    version="0.1.0",
    lifespan=lifespan,
)

# Middleware stack (order matters: first added = outermost)
_settings = get_settings()
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CorrelationIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[_settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Correlation-ID", "stripe-signature"],
)

app.include_router(me.router, prefix="/api/v1")
app.include_router(quickbooks.router, prefix="/api/v1")
app.include_router(stripe.router, prefix="/api/v1")
app.include_router(slack.router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")

@app.get("/api/v1/health", tags=["health"])
async def health() -> dict:
    """Health check — confirms the API is running."""
    return {"status": "ok"}

