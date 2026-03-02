from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import create_client

from backend.app.auth import get_current_user_id
from backend.app.config import get_settings
from backend.app.models.schemas import RunwayResponse

router = APIRouter(prefix="/cashflow", tags=["cashflow"])


def _get_supabase():
    s = get_settings()
    return create_client(s.supabase_url, s.supabase_service_role_key)


@router.get("/runway", response_model=RunwayResponse)
async def get_runway(
    current_cash: Decimal = Query(default=Decimal("0"), description="Current cash balance in USD"),
    user_id: str = Depends(get_current_user_id),
) -> RunwayResponse:
    """Calculate cash runway, burn rate, and trend from QuickBooks Cash Flow data."""
    from backend.app.services.financial import FinancialService
    from backend.app.agents.orchestrator import compiled_graph

    db = _get_supabase()
    svc = FinancialService(db)

    statements = await svc.get_statements(user_id)
    if statements is None:
        raise HTTPException(
            status_code=403,
            detail="QuickBooks not connected.",
        )

    financial_data = {
        "statements": [s.model_dump(mode="json") for s in statements],
        "current_cash": str(current_cash),
    }

    initial_state = {
        "user_id": user_id,
        "request_type": "cashflow",
        "request_params": {"months": 6, "current_cash": str(current_cash)},
        "financial_data": financial_data,
        "cache_hit": False,
        "tool_results": {},
        "model_used": "",
        "llm_analysis": "",
        "llm_numbers": {},
        "discrepancies": [],
        "output": {},
    }

    result = await compiled_graph.ainvoke(initial_state)
    output = result["output"]
    tool_results = output.get("tool_results", {})

    if "runway" not in tool_results:
        raise HTTPException(status_code=422, detail="No cash flow data available to compute runway.")

    from backend.app.models.schemas import RunwayResult
    runway = RunwayResult(**tool_results["runway"])

    return RunwayResponse(
        user_id=user_id,
        runway=runway,
        forecast_months=6,
        analysis=output.get("analysis", ""),
        model_used=output.get("model_used", ""),
        generated_at=datetime.now(timezone.utc),
    )


@router.get("/forecast")
async def get_forecast(
    months: int = Query(default=6, ge=3, le=12, description="Forecast horizon in months"),
    current_cash: Decimal = Query(default=Decimal("0")),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """3-12 month cash flow projection narrative."""
    from backend.app.services.financial import FinancialService
    from backend.app.agents.orchestrator import compiled_graph

    db = _get_supabase()
    svc = FinancialService(db)

    statements = await svc.get_statements(user_id)
    if statements is None:
        raise HTTPException(status_code=403, detail="QuickBooks not connected.")

    financial_data = {
        "statements": [s.model_dump(mode="json") for s in statements],
        "current_cash": str(current_cash),
    }

    initial_state = {
        "user_id": user_id,
        "request_type": "cashflow",
        "request_params": {"months": months, "current_cash": str(current_cash)},
        "financial_data": financial_data,
        "cache_hit": False,
        "tool_results": {},
        "model_used": "",
        "llm_analysis": "",
        "llm_numbers": {},
        "discrepancies": [],
        "output": {},
    }

    result = await compiled_graph.ainvoke(initial_state)
    output = result["output"]

    return {
        "user_id": user_id,
        "forecast_months": months,
        "analysis": output.get("analysis", ""),
        "model_used": output.get("model_used", ""),
        "tool_results": output.get("tool_results", {}),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
