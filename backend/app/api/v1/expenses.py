from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from supabase import create_client

from backend.app.auth import get_current_user_id
from backend.app.config import get_settings
from backend.app.models.schemas import ExpenseResponse, BudgetResult, AnomalyResult

router = APIRouter(prefix="/expenses", tags=["expenses"])


def _get_supabase():
    s = get_settings()
    return create_client(s.supabase_url, s.supabase_service_role_key)


@router.get("/summary", response_model=ExpenseResponse)
async def get_expense_summary(
    user_id: str = Depends(get_current_user_id),
) -> ExpenseResponse:
    """Budget vs actual, variance analysis, category breakdown with AI summary."""
    from backend.app.services.financial import FinancialService
    from backend.app.agents.orchestrator import compiled_graph

    db = _get_supabase()
    svc = FinancialService(db)

    statements = await svc.get_statements(user_id)
    if statements is None:
        raise HTTPException(status_code=403, detail="QuickBooks not connected.")

    financial_data = {
        "statements": [s.model_dump(mode="json") for s in statements],
    }

    initial_state = {
        "user_id": user_id,
        "request_type": "expense",
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

    budget = BudgetResult(**tool_results["budget"]) if "budget" in tool_results else BudgetResult(
        categories=[], top5_by_spend=[], total_expense_mom_growth=None, alerts=[]
    )
    anomalies = AnomalyResult(**tool_results["anomalies"]) if "anomalies" in tool_results else AnomalyResult(anomalies=[])

    return ExpenseResponse(
        user_id=user_id,
        budget=budget,
        anomalies=anomalies,
        summary=output.get("analysis", ""),
        model_used=output.get("model_used", ""),
        generated_at=datetime.now(timezone.utc),
    )


@router.get("/anomalies")
async def get_anomalies(
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """Z-score anomaly detection results for expense categories."""
    from backend.app.services.financial import FinancialService

    db = _get_supabase()
    svc = FinancialService(db)

    anomalies = await svc.compute_anomalies(user_id)
    if anomalies is None:
        raise HTTPException(status_code=403, detail="QuickBooks not connected.")

    return {
        "user_id": user_id,
        "anomalies": anomalies.model_dump(mode="json")["anomalies"],
        "count": len(anomalies.anomalies),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
