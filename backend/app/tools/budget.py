"""
tools/budget.py — Budget vs actual variance analysis.
Pure functions only. No LLM calls.
"""
from decimal import Decimal
from collections import defaultdict

from backend.app.models.schemas import (
    BudgetInput,
    BudgetResult,
    BudgetCategory,
    FinancialStatement,
)

_ZERO = Decimal("0")
_HUNDRED = Decimal("100")


def _expenses_by_category_and_period(
    statements: list[FinancialStatement],
) -> dict[str, dict[str, Decimal]]:
    """category -> {period -> amount} from expense / P&L statements."""
    result: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    for stmt in statements:
        if stmt.statement_type != "profit_loss":
            continue
        for row in stmt.rows:
            # Only count expense categories (not revenue/income lines)
            cat = row.category.lower()
            if any(kw in cat for kw in ("expense", "cost", "salary", "payroll", "saas", "software", "rent", "marketing", "admin")):
                result[row.category][row.period] += row.amount
    return {k: dict(v) for k, v in result.items()}


def _revenue_by_period(statements: list[FinancialStatement]) -> dict[str, Decimal]:
    by_period: dict[str, Decimal] = defaultdict(Decimal)
    for stmt in statements:
        if stmt.statement_type != "profit_loss":
            continue
        for row in stmt.rows:
            if row.category in ("Revenue", "Income"):
                by_period[row.period] += row.amount
    return dict(by_period)


def analyze_budget(inp: BudgetInput) -> BudgetResult:
    """
    Compare actual expenses against budget targets (if provided).
    Calculate MoM growth, expense-to-revenue ratios, and threshold alerts.
    """
    expense_data = _expenses_by_category_and_period(inp.statements)
    revenue_data = _revenue_by_period(inp.statements)

    # Most recent period across all categories
    all_periods: set[str] = set()
    for periods in expense_data.values():
        all_periods.update(periods.keys())

    if not all_periods:
        return BudgetResult(
            categories=[],
            top5_by_spend=[],
            total_expense_mom_growth=None,
            alerts=[],
        )

    sorted_periods = sorted(all_periods)
    current_period = sorted_periods[-1]
    prev_period = sorted_periods[-2] if len(sorted_periods) >= 2 else None

    current_revenue = revenue_data.get(current_period, _ZERO)
    prev_revenue = revenue_data.get(prev_period, _ZERO) if prev_period else _ZERO

    categories: list[BudgetCategory] = []
    global_alerts: list[str] = []

    total_current = _ZERO
    total_prev = _ZERO

    for cat, periods in expense_data.items():
        actual = periods.get(current_period, _ZERO)
        budget = inp.budget_targets.get(cat, _ZERO) if inp.budget_targets else _ZERO
        prev_actual = periods.get(prev_period, _ZERO) if prev_period else None

        # Variance
        if budget > _ZERO:
            variance_pct = (actual - budget) / budget * _HUNDRED
        else:
            variance_pct = _ZERO

        # MoM growth
        mom_growth = None
        if prev_actual is not None and prev_actual > _ZERO:
            mom_growth = (actual - prev_actual) / prev_actual * _HUNDRED

        # Expense to revenue ratio
        expense_to_revenue_pct = None
        if current_revenue > _ZERO:
            expense_to_revenue_pct = actual / current_revenue * _HUNDRED

        # Alert level
        if variance_pct > Decimal("50"):
            alert_level = "CRITICAL"
            global_alerts.append(f"{cat} is {variance_pct:.0f}% over budget (CRITICAL)")
        elif variance_pct > Decimal("20"):
            alert_level = "WARNING"
            global_alerts.append(f"{cat} is {variance_pct:.0f}% over budget (WARNING)")
        else:
            alert_level = "OK"

        categories.append(BudgetCategory(
            category=cat,
            actual=actual,
            budget=budget,
            variance_pct=variance_pct,
            mom_growth=mom_growth,
            expense_to_revenue_pct=expense_to_revenue_pct,
            alert=alert_level,
        ))

        total_current += actual
        if prev_actual is not None:
            total_prev += prev_actual

    # Sort by actual spend descending for top 5
    categories.sort(key=lambda c: c.actual, reverse=True)
    top5 = [c.category for c in categories[:5]]

    # Total expense MoM growth
    total_expense_mom_growth = None
    if total_prev > _ZERO:
        total_expense_mom_growth = (total_current - total_prev) / total_prev * _HUNDRED

    # Check if expenses growing faster than revenue for 2+ months
    if len(sorted_periods) >= 3 and current_revenue > _ZERO and prev_revenue > _ZERO:
        rev_growth = (current_revenue - prev_revenue) / prev_revenue * _HUNDRED
        if total_expense_mom_growth is not None and total_expense_mom_growth > rev_growth:
            global_alerts.append("Total expenses growing faster than revenue")

    return BudgetResult(
        categories=categories,
        top5_by_spend=top5,
        total_expense_mom_growth=total_expense_mom_growth,
        alerts=global_alerts,
    )
