from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.v1.reports import router as reports_router
from backend.app.api.v1.cashflow import router as cashflow_router
from backend.app.api.v1.expenses import router as expenses_router
from backend.app.api.v1.quickbooks import router as quickbooks_router
from backend.app.api.v1.slack import router as slack_router

app = FastAPI(
    title="Flowytics",
    description="Agentic CFO — NeuroSymbolic AI for startup finance",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(reports_router, prefix="/api/v1")
app.include_router(cashflow_router, prefix="/api/v1")
app.include_router(expenses_router, prefix="/api/v1")
app.include_router(quickbooks_router, prefix="/api/v1")
app.include_router(slack_router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "version": "0.1.0"}
