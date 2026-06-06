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
    financials = sorted(summary.monthly_financials, key=lambda x: x.month_start)
    if len(financials) < 3:
        # Cannot calculate Z-score reliably with fewer than 3 months of data
        return clean_unicode_minus(AnomalyResult(anomalies=[], scan_period_months=len(financials)))

    # Get the the target month to scan (the most recent month)
    target = financials[-1]
    history = financials[:-1]

    category_history = defaultdict(list)
    for m in history:
        for cat, amt in m.category_expenses.items():
            category_history[cat].append(amt)

    anomalies = []
    
    for cat, current_amount in target.category_expenses.items():
        hist_amounts = category_history.get(cat, [])
        if len(hist_amounts) < 2:
            continue
            
        mean = Decimal(str(statistics.mean(hist_amounts)))
        stdev = Decimal(str(statistics.stdev(hist_amounts))) if len(hist_amounts) > 1 else Decimal("0")
        
        if stdev == Decimal("0"):
            # Avoid division by zero. If history is totally flat, check absolute change.
            if current_amount > mean * Decimal("1.5") and current_amount - mean > Decimal("1000"):
                z_score = Decimal("99.9") # artificial high z-score for sudden spike
            else:
                continue
        else:
            z_score = (current_amount - mean) / stdev

        # Look for spikes ONLY (positive Z-curves in expenses)
        if z_score > Decimal("2.0"):
            severity = "critical" if z_score > Decimal("3.0") else "warning"
            
            anomalies.append(Anomaly(
                category=cat,
                current_amount=current_amount.quantize(Decimal("0.01")),
                historical_mean=mean.quantize(Decimal("0.01")),
                z_score=z_score.quantize(Decimal("0.01")),
                severity=severity,
                description=f"Expense category '{cat}' spiked to ${current_amount:,.2f} versus a historical average of ${mean:,.2f}."
            ))

    return clean_unicode_minus(AnomalyResult(
        anomalies=anomalies,
        scan_period_months=len(financials)
    ))
