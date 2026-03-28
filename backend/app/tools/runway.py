from datetime import date
from decimal import Decimal
from dateutil.relativedelta import relativedelta
from langchain_core.tools import tool
from backend.app.tools.schemas import BurnRateResult, FinancialSummary, RunwayResult

@tool
def calculate_runway(summary: FinancialSummary, burn_rate: BurnRateResult) -> RunwayResult:
    """
    Calculates runway months and categorizes health status based on current cash and net burn.
    """
    cash = summary.current_cash_balance
    net_burn = burn_rate.net_burn_monthly

    if net_burn <= Decimal("0"):
        return RunwayResult(
            runway_months=Decimal("9999"),
            cash_balance=cash,
            monthly_net_burn=net_burn,
            runway_status="healthy",
            cash_zero_date=None
        )

    # Negative cash = already past zero
    if cash <= Decimal("0"):
        return RunwayResult(
            runway_months=Decimal("0"),
            cash_balance=cash,
            monthly_net_burn=net_burn,
            runway_status="critical",
            cash_zero_date=date.today()
        )

    runway_months = cash / net_burn
    
    if runway_months < Decimal("3"):
        status = "critical"
    elif runway_months < Decimal("6"):
        status = "warning"
    elif runway_months < Decimal("12"):
        status = "monitor"
    else:
        status = "healthy"

    months = int(runway_months)
    # remaining fraction of a month approx 30 days
    days = int((runway_months - Decimal(str(months))) * Decimal("30"))
    
    try:
        zero_date = date.today() + relativedelta(months=months, days=days)
    except Exception:
        zero_date = None

    # Handle float conversion precision issues if any, round to 2 decimal places
    runway_months = runway_months.quantize(Decimal("0.01"))

    return RunwayResult(
        runway_months=runway_months,
        cash_balance=cash,
        monthly_net_burn=net_burn,
        runway_status=status,
        cash_zero_date=zero_date
    )
