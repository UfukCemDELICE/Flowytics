from datetime import date
from decimal import Decimal

from langchain_core.tools import tool
from backend.app.tools.schemas import BurnRateResult, FinancialSummary

from backend.app.utils import clean_unicode_minus

@tool
def calculate_burn_rate(summary: FinancialSummary) -> BurnRateResult:
    """
    Calculates the burn rate (net and gross) given historical monthly financial data.
    - Restricts calculation to the last 3 FULL months of activity.
    - Excludes leading zero-revenue months and the current partial month.
    - Populates burn_multiple using the full active period.
    """
    sorted_financials = sorted(summary.monthly_financials, key=lambda x: x.month_start)
    
    # 1. Exclude current partial month
    today = date.today()
    full_months = [
        m for m in sorted_financials
        if not (m.month_start.year == today.year and m.month_start.month == today.month)
    ]
    
    # 2. Exclude leading zero-revenue months
    first_rev_idx = None
    for idx, m in enumerate(full_months):
        if m.total_revenue > 0:
            first_rev_idx = idx
            break
            
    if first_rev_idx is not None:
        active_months = full_months[first_rev_idx:]
    else:
        active_months = full_months

    n = len(active_months)
    if n == 0:
        return clean_unicode_minus(BurnRateResult(
            net_burn_monthly=Decimal("0"),
            gross_burn_monthly=Decimal("0"),
            burn_multiple=None,
            trend="stable",
            trend_slope=Decimal("0"),
            period_months=0
        ))

    # We use the most recent 3 months of active_months for burn rate averages & regression
    recent_months = active_months[-3:]
    n_rec = len(recent_months)
    
    total_net_burn = sum(-m.net_income for m in recent_months)
    net_burn_monthly = total_net_burn / Decimal(str(n_rec))
    
    total_gross_burn = sum(m.total_expenses for m in recent_months)
    gross_burn_monthly = total_gross_burn / Decimal(str(n_rec))

    # Calculate trend using basic linear regression for net_burn over recent_months
    x = [Decimal(str(i)) for i in range(n_rec)]
    y = [-m.net_income for m in recent_months]
    
    sum_x = sum(x)
    sum_y = sum(y)
    sum_xy = sum(xi * yi for xi, yi in zip(x, y))
    sum_x2 = sum(xi * xi for xi in x)

    n_dec = Decimal(str(n_rec))
    denominator = (n_dec * sum_x2 - sum_x * sum_x)
    
    if denominator == 0:
        slope = Decimal("0")
    else:
        slope = (n_dec * sum_xy - sum_x * sum_y) / denominator

    mean_burn = sum_y / n_dec if n_dec > 0 else Decimal("0")
    threshold = abs(mean_burn) * Decimal("0.05")
    
    if slope > threshold:
        trend = "increasing"
    elif slope < -threshold:
        trend = "decreasing"
    else:
        trend = "stable"

    # Calculate burn_multiple over the full active period
    # first_rev_month = first month with non-zero subscription revenue
    # latest_full_month = most recent FULL month
    burn_multiple = None
    if first_rev_idx is not None and len(active_months) > 0:
        first_rev_month = active_months[0]
        latest_full_month = active_months[-1]
        
        first_mrr = first_rev_month.total_revenue
        latest_mrr = latest_full_month.total_revenue
        net_new_ARR = (latest_mrr * Decimal("12")) - (first_mrr * Decimal("12"))
        
        if net_new_ARR > 0:
            total_net_burn_active = abs(sum(m.net_income for m in active_months))
            burn_multiple = total_net_burn_active / net_new_ARR
            burn_multiple = burn_multiple.quantize(Decimal("0.01"))

    return clean_unicode_minus(BurnRateResult(
        net_burn_monthly=net_burn_monthly,
        gross_burn_monthly=gross_burn_monthly,
        burn_multiple=burn_multiple,
        trend=trend,
        trend_slope=slope,
        period_months=n_rec
    ))

