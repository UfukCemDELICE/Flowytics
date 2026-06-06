from decimal import Decimal
from langchain_core.tools import tool
from backend.app.tools.schemas import FinancialSummary, RunRateResult, RunRateMonth

@tool
def calculate_run_rate(summary: FinancialSummary) -> RunRateResult:
    """
    Calculates the annualized run rate (ARR proxy) based on the most recent 3 months of populated revenue data.
    """
    financials = sorted(summary.monthly_financials, key=lambda x: x.month_start)
    
    # Take the last 3 entries
    selected_months = financials[-3:]
    count = len(selected_months)

    if count == 0:
        return RunRateResult(
            run_rate=None,
            months_used=[],
            month_count=0,
            low_confidence=True,
            is_volatile=False,
            volatility_ratio=Decimal("0"),
            min_revenue=Decimal("0"),
            max_revenue=Decimal("0"),
            caveat="No revenue data is available to calculate a run rate."
        )

    low_confidence = (count < 3)

    sum_revenue = sum(m.total_revenue for m in selected_months)
    mean_rev = sum_revenue / Decimal(str(count))
    run_rate = mean_rev * Decimal("12")
    # Ensure run_rate is rounded to 2 decimal places to match test expectation exactly
    run_rate = run_rate.quantize(Decimal("0.01"))

    min_rev = min(m.total_revenue for m in selected_months)
    max_rev = max(m.total_revenue for m in selected_months)

    if mean_rev == Decimal("0"):
        volatility_ratio = Decimal("0")
    else:
        volatility_ratio = (max_rev - min_rev) / mean_rev
        
    is_volatile = volatility_ratio > Decimal("0.5")

    caveat = (
        f"This is an annualized run rate based on your last {count} month(s) of revenue, not true ARR. "
        "It assumes current revenue recurs at the same level. True ARR requires separating recurring "
        "(subscription) revenue from one-time revenue, which isn't tagged in your QuickBooks chart of "
        "accounts."
    )
    if is_volatile:
        caveat += f" Note: monthly revenue varied significantly (low: ${min_rev:,.2f}, high: ${max_rev:,.2f}); treat this as a rough directional figure."

    months_used = [
        RunRateMonth(month_start=m.month_start, total_revenue=m.total_revenue)
        for m in selected_months
    ]

    return RunRateResult(
        run_rate=run_rate,
        months_used=months_used,
        month_count=count,
        low_confidence=low_confidence,
        is_volatile=is_volatile,
        volatility_ratio=volatility_ratio,
        min_revenue=min_rev,
        max_revenue=max_rev,
        caveat=caveat
    )
