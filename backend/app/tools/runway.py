"""
tools/runway.py — Burn rate and runway calculations.
Pure functions only. No LLM calls.
"""
from datetime import date, timedelta
from decimal import Decimal
from collections import defaultdict

from backend.app.models.schemas import (
    RunwayInput,
    RunwayResult,
    RunwayAlert,
    FinancialStatement,
)

_ZERO = Decimal("0")


def _net_cash_outflow_by_period(stmt: FinancialStatement) -> dict[str, Decimal]:
    """Return net cash outflow (positive = burning cash) per period."""
    by_period: dict[str, Decimal] = defaultdict(Decimal)
    for row in stmt.rows:
        by_period[row.period] += row.amount
    # Net outflow = negative of net cash flow (spending > income → positive burn)
    return {p: -v for p, v in by_period.items()}


def _linear_regression_slope(values: list[Decimal]) -> Decimal:
    """Simple linear regression slope over index positions."""
    n = len(values)
    if n < 2:
        return _ZERO
    x_mean = Decimal(n - 1) / Decimal(2)
    y_mean = sum(values) / Decimal(n)
    numerator = sum((Decimal(i) - x_mean) * (v - y_mean) for i, v in enumerate(values))
    denominator = sum((Decimal(i) - x_mean) ** 2 for i in range(n))
    if denominator == _ZERO:
        return _ZERO
    return numerator / denominator


def calculate_runway(inp: RunwayInput) -> RunwayResult:
    """
    Calculate burn rate, runway, and cash zero date.

    Burn rate = average net cash outflow over last 3 months.
    Weighted burn rate weights recent months more heavily (exponential decay).
    Runway = current_cash / monthly_burn_rate.
    """
    outflows = _net_cash_outflow_by_period(inp.cash_flow_statement)
    periods = sorted(outflows.keys())

    if not periods:
        alert = RunwayAlert(level="CRITICAL", message="No cash flow data available.")
        return RunwayResult(
            monthly_burn_rate=_ZERO,
            runway_months=None,
            weighted_burn_rate=_ZERO,
            burn_trend="stable",
            cash_zero_date=None,
            alert=alert,
        )

    # Use last 3 months for burn rate (or fewer if not available)
    recent = periods[-3:]
    recent_outflows = [outflows[p] for p in recent]

    # Simple average burn rate
    monthly_burn_rate = sum(recent_outflows) / Decimal(len(recent_outflows))

    # Weighted burn rate (exponential decay: most recent gets highest weight)
    weights = [Decimal(2 ** i) for i in range(len(recent_outflows))]
    total_weight = sum(weights)
    weighted_burn_rate = sum(w * v for w, v in zip(weights, recent_outflows)) / total_weight

    # Burn trend via linear regression slope over all available periods
    all_outflows = [outflows[p] for p in periods]
    slope = _linear_regression_slope(all_outflows)
    if slope > Decimal("0.05") * (sum(all_outflows) / Decimal(len(all_outflows)) or Decimal(1)):
        burn_trend = "increasing"
    elif slope < Decimal("-0.05") * (sum(all_outflows) / Decimal(len(all_outflows)) or Decimal(1)):
        burn_trend = "decreasing"
    else:
        burn_trend = "stable"

    # Runway
    if monthly_burn_rate <= _ZERO:
        # Company is cash flow positive
        runway_months = None
        cash_zero_date = None
        alert = RunwayAlert(level="OK", message="Company is cash flow positive — no burn.")
    else:
        runway_months = inp.current_cash / monthly_burn_rate
        months_int = int(runway_months)
        zero_date = date.today() + timedelta(days=months_int * 30)
        cash_zero_date = zero_date

        if runway_months < Decimal("3"):
            alert = RunwayAlert(level="CRITICAL", message=f"Only {runway_months:.1f} months of runway remaining.")
        elif runway_months < Decimal("6"):
            alert = RunwayAlert(level="WARNING", message=f"{runway_months:.1f} months runway — start fundraising.")
        elif runway_months < Decimal("12"):
            alert = RunwayAlert(level="INFO", message=f"{runway_months:.1f} months runway — monitor closely.")
        else:
            alert = RunwayAlert(level="OK", message=f"{runway_months:.1f} months runway — healthy.")

    # Burn rate increasing > 20% MoM check
    if len(recent_outflows) >= 2:
        last, prev = recent_outflows[-1], recent_outflows[-2]
        if prev > _ZERO and (last - prev) / prev > Decimal("0.20"):
            if alert.level == "OK":
                alert = RunwayAlert(level="WARNING", message="Burn rate increasing >20% MoM.")

    return RunwayResult(
        monthly_burn_rate=monthly_burn_rate,
        runway_months=runway_months,
        weighted_burn_rate=weighted_burn_rate,
        burn_trend=burn_trend,
        cash_zero_date=cash_zero_date,
        alert=alert,
    )
