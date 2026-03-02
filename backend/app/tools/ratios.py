"""
tools/ratios.py — Deterministic financial ratio calculations.
Pure functions only. No LLM calls. Same input → same output, always.
"""
from decimal import Decimal, InvalidOperation
from collections import defaultdict

from backend.app.models.schemas import (
    RatioInput,
    RatioResult,
    FinancialStatement,
)

_ZERO = Decimal("0")
_HUNDRED = Decimal("100")


def _safe_div(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    """Return numerator/denominator or None if denominator is zero."""
    if denominator == _ZERO:
        return None
    return numerator / denominator


def _rows_by_category(stmt: FinancialStatement) -> dict[str, Decimal]:
    """Sum all amounts per top-level category for the most recent period."""
    if not stmt.rows:
        return {}
    latest_period = max(r.period for r in stmt.rows)
    totals: dict[str, Decimal] = defaultdict(Decimal)
    for row in stmt.rows:
        if row.period == latest_period:
            totals[row.category] += row.amount
    return dict(totals)


def _rows_by_period(stmt: FinancialStatement) -> dict[str, dict[str, Decimal]]:
    """period -> {category -> total_amount}"""
    by_period: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    for row in stmt.rows:
        by_period[row.period][row.category] += row.amount
    return {p: dict(cats) for p, cats in by_period.items()}


def calculate_ratios(inp: RatioInput) -> RatioResult:
    """
    Calculate all financial ratios from P&L and Balance Sheet statements.
    Returns RatioResult with every computable ratio populated.
    """
    pl = next((s for s in inp.statements if s.statement_type == "profit_loss"), None)
    bs = next((s for s in inp.statements if s.statement_type == "balance_sheet"), None)

    period = (pl or bs).period_end.strftime("%Y-%m") if (pl or bs) else "unknown"

    # --- P&L ratios ---
    gross_margin = net_margin = operating_margin = None
    mom_revenue_growth = yoy_revenue_growth = None
    arr = mrr = net_revenue_retention = None

    if pl:
        pl_current = _rows_by_category(pl)
        revenue = pl_current.get("Revenue", pl_current.get("Income", _ZERO))
        cogs = pl_current.get("Cost of Goods Sold", pl_current.get("COGS", _ZERO))
        net_income = pl_current.get("Net Income", pl_current.get("Net Profit", _ZERO))
        operating_income = pl_current.get("Operating Income", pl_current.get("Operating Profit", None))

        gross_profit = revenue - cogs
        gross_margin = _safe_div(gross_profit, revenue)
        net_margin = _safe_div(net_income, revenue)
        if operating_income is not None:
            operating_margin = _safe_div(operating_income, revenue)

        # MoM / YoY revenue growth from period-level data
        by_period = _rows_by_period(pl)
        periods = sorted(by_period.keys())
        if len(periods) >= 2:
            current_rev = by_period[periods[-1]].get("Revenue", by_period[periods[-1]].get("Income", _ZERO))
            prev_rev = by_period[periods[-2]].get("Revenue", by_period[periods[-2]].get("Income", _ZERO))
            mom_revenue_growth = _safe_div(current_rev - prev_rev, prev_rev)

        if len(periods) >= 13:
            yoy_period = periods[-13]
            yoy_rev = by_period[yoy_period].get("Revenue", by_period[yoy_period].get("Income", _ZERO))
            yoy_revenue_growth = _safe_div(current_rev - yoy_rev, yoy_rev)

        # SaaS: if MRR is available as a category
        mrr_val = pl_current.get("MRR", pl_current.get("Monthly Recurring Revenue", None))
        if mrr_val is not None:
            mrr = mrr_val
            arr = mrr * Decimal("12")

    # --- Balance Sheet ratios ---
    current_ratio = quick_ratio = debt_to_equity = None

    if bs:
        bs_current = _rows_by_category(bs)
        current_assets = bs_current.get("Current Assets", _ZERO)
        current_liabilities = bs_current.get("Current Liabilities", _ZERO)
        inventory = bs_current.get("Inventory", _ZERO)
        total_liabilities = bs_current.get("Total Liabilities", bs_current.get("Liabilities", _ZERO))
        total_equity = bs_current.get("Total Equity", bs_current.get("Equity", _ZERO))

        current_ratio = _safe_div(current_assets, current_liabilities)
        quick_ratio = _safe_div(current_assets - inventory, current_liabilities)
        debt_to_equity = _safe_div(total_liabilities, total_equity)

    # --- Revenue per employee ---
    revenue_per_employee = None
    if inp.headcount and pl and revenue > _ZERO:
        revenue_per_employee = _safe_div(revenue, Decimal(inp.headcount))

    return RatioResult(
        gross_margin=gross_margin,
        net_margin=net_margin,
        operating_margin=operating_margin,
        current_ratio=current_ratio,
        quick_ratio=quick_ratio,
        debt_to_equity=debt_to_equity,
        mom_revenue_growth=mom_revenue_growth,
        yoy_revenue_growth=yoy_revenue_growth,
        revenue_per_employee=revenue_per_employee,
        arr=arr,
        mrr=mrr,
        net_revenue_retention=net_revenue_retention,
        period=period,
    )
