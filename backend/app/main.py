from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.v1 import me, quickbooks, stripe, slack


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup: scheduler and Slack bot will be initialised here
    yield
    # Shutdown: cleanup goes here


app = FastAPI(
    title="Flowytics API",
    description="Agentic CFO — AI-powered managerial accounting for startups",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(me.router, prefix="/api/v1")
app.include_router(quickbooks.router, prefix="/api/v1")
app.include_router(stripe.router, prefix="/api/v1")
app.include_router(slack.router, prefix="/api/v1")


from fastapi.responses import RedirectResponse

@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")

@app.get("/api/v1/health", tags=["health"])
async def health() -> dict:
    """Health check — confirms the API is running."""
    return {"status": "ok"}
