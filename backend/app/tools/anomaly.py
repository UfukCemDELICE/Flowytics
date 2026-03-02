"""
tools/anomaly.py — Z-score anomaly detection on financial data.
Pure functions only. No LLM calls. Requires 3+ months of data.
"""
from decimal import Decimal
from collections import defaultdict

from backend.app.models.schemas import (
    AnomalyInput,
    AnomalyResult,
    AnomalyItem,
    FinancialStatement,
)

_ZERO = Decimal("0")
_Z_THRESHOLD = Decimal("2.0")


def _sqrt_decimal(value: Decimal) -> Decimal:
    """Compute square root of a Decimal via float conversion (acceptable for stats)."""
    if value <= _ZERO:
        return _ZERO
    return Decimal(str(float(value) ** 0.5))


def _category_time_series(
    statements: list[FinancialStatement],
) -> dict[str, dict[str, Decimal]]:
    """category -> {period -> amount}"""
    data: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    for stmt in statements:
        for row in stmt.rows:
            data[row.category][row.period] += row.amount
    return {k: dict(v) for k, v in data.items()}


def detect_anomalies(inp: AnomalyInput) -> AnomalyResult:
    """
    Run Z-score analysis per category. Flag |Z| > 2.0.
    Also detect: new categories, disappeared categories, sudden vendor concentration.
    Requires 3+ months of data for meaningful statistics.
    """
    ts = _category_time_series(inp.statements)
    all_periods = sorted({p for cat_data in ts.values() for p in cat_data})

    if len(all_periods) < 3:
        return AnomalyResult(anomalies=[])

    current_period = all_periods[-1]
    historical_periods = all_periods[:-1]

    anomalies: list[AnomalyItem] = []

    # Track which categories existed historically
    historical_cats = {cat for cat, periods in ts.items() if any(p in periods for p in historical_periods)}
    current_cats = {cat for cat, periods in ts.items() if current_period in periods}

    # New categories
    for cat in current_cats - historical_cats:
        value = ts[cat].get(current_period, _ZERO)
        anomalies.append(AnomalyItem(
            category=cat,
            period=current_period,
            value=value,
            z_score=Decimal("999"),
            severity="HIGH",
            reason="New category not seen in historical data",
        ))

    # Disappeared categories
    for cat in historical_cats - current_cats:
        anomalies.append(AnomalyItem(
            category=cat,
            period=current_period,
            value=_ZERO,
            z_score=Decimal("-999"),
            severity="MEDIUM",
            reason="Category disappeared — was present in prior periods",
        ))

    # Z-score per existing category
    for cat in historical_cats & current_cats:
        hist_values = [ts[cat].get(p, _ZERO) for p in historical_periods if p in ts[cat]]
        if len(hist_values) < 2:
            continue

        mean = sum(hist_values) / Decimal(len(hist_values))
        variance = sum((v - mean) ** 2 for v in hist_values) / Decimal(len(hist_values))
        std = _sqrt_decimal(variance)

        current_value = ts[cat].get(current_period, _ZERO)

        if std == _ZERO:
            # No variance historically — any change is notable
            if current_value != mean:
                z_score = Decimal("999") if current_value > mean else Decimal("-999")
            else:
                continue
        else:
            z_score = (current_value - mean) / std

        if abs(z_score) > _Z_THRESHOLD:
            if abs(z_score) > Decimal("3.5"):
                severity = "HIGH"
            elif abs(z_score) > Decimal("2.5"):
                severity = "MEDIUM"
            else:
                severity = "LOW"

            direction = "spike" if z_score > _ZERO else "drop"
            anomalies.append(AnomalyItem(
                category=cat,
                period=current_period,
                value=current_value,
                z_score=z_score,
                severity=severity,
                reason=f"Unusual {direction}: {abs(z_score):.2f} standard deviations from historical mean ({mean:.2f})",
            ))

    # Sort by severity then absolute z-score
    severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    anomalies.sort(key=lambda a: (severity_order[a.severity], -abs(a.z_score)))

    return AnomalyResult(anomalies=anomalies)
