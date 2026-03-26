from langchain_core.tools import tool
from typing import Dict, Any

@tool
def generate_monthly_report(tenant_id: str = "default") -> Dict[str, Any]:
    """
    Generates a comprehensive monthly financial report by pulling high-level 
    cash, burn, runway, and major outlier data for the current month.
    """
    # In a real implementation, this would aggregate actual data from the DB/QBO
    return {
        "status": "success",
        "report_month": "Current",
        "executive_summary": "Financial position remains stable with 9.3 months of runway. Net burn has increased 18% due to recent operational expenses.",
        "key_metrics": {
            "current_cash": 383000.0,
            "net_burn": 41200.0,
            "runway_months": 9.3,
            "gross_margin_pct": 72.0
        },
        "top_expenses": [
            {"category": "Payroll", "amount": 25000.0, "trend": "up 15%"},
            {"category": "Software Subscriptions", "amount": 4200.0, "trend": "stable"}
        ],
        "recommendation": "Monitor hiring velocity to preserve 6+ month runway threshold."
    }
