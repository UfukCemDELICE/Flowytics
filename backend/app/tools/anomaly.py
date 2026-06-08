from datetime import date
from decimal import Decimal
from collections import defaultdict
import statistics
from langchain_core.tools import tool
from backend.app.tools.schemas import FinancialSummary, AnomalyResult, Anomaly

from backend.app.utils import clean_unicode_minus

@tool
def calculate_anomalies(summary: FinancialSummary) -> AnomalyResult:
    """
    Detects unusual statistical spikes in monthly expense categories using Z-score logic.
    |Z-score| > 2.0 triggers a warning.
    |Z-score| > 3.0 triggers a critical.
    """
    today = date.today()
    sorted_financials = sorted(summary.monthly_financials, key=lambda x: x.month_start)
    financials = [
        m for m in sorted_financials
        if not (m.month_start.year == today.year and m.month_start.month == today.month)
    ]
    if len(financials) < 3:
        # Cannot calculate Z-score reliably with fewer than 3 months of data
        return clean_unicode_minus(AnomalyResult(anomalies=[], scan_period_months=len(financials)))

    anomalies = []
    
    # Scan each month starting from the point where there are >= 2 prior months of history
    # i.e., index 2 to len(financials) - 1
    for i in range(2, len(financials)):
        target = financials[i]
        history = financials[:i]

        category_history = defaultdict(list)
        for m in history:
            for cat, amt in m.category_expenses.items():
                category_history[cat].append(amt)

        MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        month_str = f"{MONTHS[target.month_start.month - 1]} {target.month_start.year}"

        for cat, current_amount in target.category_expenses.items():
            hist_amounts = category_history.get(cat, [])
            if len(hist_amounts) < 2:
                continue
                
            mean = Decimal(str(statistics.mean(hist_amounts)))
            stdev = Decimal(str(statistics.stdev(hist_amounts))) if len(hist_amounts) > 1 else Decimal("0")
            
            # Trailing 3-month average calculation
            trailing_months = history[-3:]
            trailing_amounts = [m.category_expenses.get(cat, Decimal("0")) for m in trailing_months]
            trailing_avg = Decimal(str(statistics.mean(trailing_amounts))) if trailing_amounts else Decimal("0")
            
            is_fallback_spike = False
            if trailing_avg > Decimal("0") and current_amount > trailing_avg * Decimal("2.5"):
                is_fallback_spike = True

            if stdev == Decimal("0"):
                # Avoid division by zero. If history is totally flat, check absolute change.
                if current_amount > mean * Decimal("1.5") and current_amount - mean > Decimal("1000"):
                    z_score = Decimal("99.9") # artificial high z-score for sudden spike
                elif is_fallback_spike:
                    z_score = Decimal("99.9")
                else:
                    continue
            else:
                z_score = (current_amount - mean) / stdev

            # Look for spikes ONLY (positive Z-curves in expenses)
            if z_score > Decimal("2.0") or is_fallback_spike:
                severity = "critical" if z_score > Decimal("3.0") else "warning"
                
                anomalies.append(Anomaly(
                    category=cat,
                    current_amount=current_amount.quantize(Decimal("0.01")),
                    historical_mean=mean.quantize(Decimal("0.01")),
                    z_score=z_score.quantize(Decimal("0.01")),
                    severity=severity,
                    month=month_str,
                    description=f"{month_str}: '{cat}' spiked to ${current_amount:,.0f} vs avg ${mean:,.0f}"
                ))

    return clean_unicode_minus(AnomalyResult(
        anomalies=anomalies,
        scan_period_months=len(financials) - 2
    ))
