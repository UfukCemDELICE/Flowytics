from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


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
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/health", tags=["health"])
async def health() -> dict:
    """Health check — confirms the API is running."""
    return {"status": "ok"}
