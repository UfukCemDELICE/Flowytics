from decimal import Decimal

from langchain_core.tools import tool
from backend.app.tools.schemas import BurnRateResult, FinancialSummary

@tool
def calculate_burn_rate(summary: FinancialSummary) -> BurnRateResult:
    """
    Calculates the burn rate (net and gross) given historical monthly financial data.
    - Uses weighted average (recent months weighted more).
    - Checks linear regression for slope to determine 'increasing', 'stable', or 'decreasing'.
    """
    financials = sorted(summary.monthly_financials, key=lambda x: x.month_start)
    n = len(financials)
    
    if n == 0:
        return BurnRateResult(
            net_burn_monthly=Decimal("0"),
            gross_burn_monthly=Decimal("0"),
            burn_multiple=None,
            trend="stable",
            trend_slope=Decimal("0"),
            period_months=0
        )

    # Weighted average: more recent months carry higher weight (e.g., exponential or linear decay)
    # Let's use linear weights: 1, 2, 3...
    total_net_burn = Decimal("0")
    total_gross_burn = Decimal("0")
    weight_sum = Decimal("0")

    # Arrays for linear regression
    x = []
    y = []

    for i, data in enumerate(financials):
        # Burn is negative net income (if net income is -10K, burn is 10K)
        # If net income is positive, burn is 0 or negative. We'll use actual values.
        net_burn = -data.net_income
        gross_burn = data.total_expenses
        
        # We'll weigh the last half of the data at 2x, as suggested by 'recent months weighted 2x'
        # Let's just do a simple weighting: older half = 1x, newer half = 2x
        weight = Decimal("2") if i >= n / 2 else Decimal("1")
        
        total_net_burn += net_burn * weight
        total_gross_burn += gross_burn * weight
        weight_sum += weight

        x.append(Decimal(str(i)))
        y.append(net_burn)

    net_burn_monthly = total_net_burn / weight_sum
    gross_burn_monthly = total_gross_burn / weight_sum

    # Calculate trend using basic linear regression for net_burn
    # slope = (n * sum(xy) - sum(x)*sum(y)) / (n * sum(x^2) - sum(x)^2)
    sum_x = sum(x)
    sum_y = sum(y)
    sum_xy = sum(xi * yi for xi, yi in zip(x, y))
    sum_x2 = sum(xi * xi for xi in x)

    n_dec = Decimal(str(n))
    denominator = (n_dec * sum_x2 - sum_x * sum_x)
    
    if denominator == 0:
        slope = Decimal("0")
    else:
        slope = (n_dec * sum_xy - sum_x * sum_y) / denominator

    # Determine trend categorical
    # mean of y
    mean_burn = sum_y / n_dec if n_dec > 0 else Decimal("0")
    
    threshold = abs(mean_burn) * Decimal("0.05")
    
    if slope > threshold:
        trend = "increasing"
    elif slope < -threshold:
        trend = "decreasing"
    else:
        trend = "stable"

    # Burn multiple = net burn / net new ARR. We skip ARR logic for now unless there's an easy way.
    # SaaS metric, leaving as None.
    
    return BurnRateResult(
        net_burn_monthly=net_burn_monthly,
        gross_burn_monthly=gross_burn_monthly,
        burn_multiple=None,
        trend=trend,
        trend_slope=slope,
        period_months=n
    )
