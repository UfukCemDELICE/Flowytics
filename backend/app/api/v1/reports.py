from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from supabase import create_client

from backend.app.auth import get_current_user_id
from backend.app.config import get_settings
from backend.app.models.schemas import ReportResponse, RatioResult, RunwayResult, BudgetResult, AnomalyResult

router = APIRouter(prefix="/reports", tags=["reports"])


def _get_supabase():
    s = get_settings()
    return create_client(s.supabase_url, s.supabase_service_role_key)


@router.get("/financial", response_model=ReportResponse)
async def get_financial_report(
    user_id: str = Depends(get_current_user_id),
) -> ReportResponse:
    """Full P&L, Balance Sheet, and Cash Flow analysis with KPIs and AI narrative."""
    from backend.app.services.financial import FinancialService
    from backend.app.agents.orchestrator import compiled_graph

    db = _get_supabase()
    svc = FinancialService(db)

    statements = await svc.get_statements(user_id)
    if statements is None:
        raise HTTPException(
            status_code=403,
            detail="QuickBooks not connected. Please connect at /api/v1/quickbooks/authorize.",
        )

    financial_data = {
        "statements": [s.model_dump(mode="json") for s in statements],
        "current_cash": "0",
    }

    initial_state = {
        "user_id": user_id,
        "request_type": "report",
        "request_params": {},
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

    ratios = RatioResult(**tool_results["ratios"]) if "ratios" in tool_results else None
    runway = RunwayResult(**tool_results["runway"]) if "runway" in tool_results else None
    budget = BudgetResult(**tool_results["budget"]) if "budget" in tool_results else None
    anomalies = AnomalyResult(**tool_results["anomalies"]) if "anomalies" in tool_results else None

    return ReportResponse(
        user_id=user_id,
        report_type="financial",
        ratios=ratios,
        runway=runway,
        budget=budget,
        anomalies=anomalies,
        analysis=output.get("analysis", ""),
        model_used=output.get("model_used", ""),
        discrepancies=output.get("discrepancies", []),
        generated_at=datetime.now(timezone.utc),
    )
