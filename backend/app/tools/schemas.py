from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

class MonthlyFinancial(BaseModel):
    month_start: date
    total_revenue: Decimal
    total_expenses: Decimal
    net_income: Decimal
    category_expenses: dict[str, Decimal] = Field(default_factory=dict)

class BurnRateResult(BaseModel):
    net_burn_monthly: Decimal
    gross_burn_monthly: Decimal
    burn_multiple: Decimal | None
    trend: Literal["increasing", "stable", "decreasing"]
    trend_slope: Decimal
    period_months: int

class RunwayResult(BaseModel):
    runway_months: Decimal
    cash_balance: Decimal
    monthly_net_burn: Decimal
    runway_status: Literal["critical", "warning", "monitor", "healthy"]
    cash_zero_date: date | None

class WeekProjection(BaseModel):
    week_start: date
    projected_inflow: Decimal
    projected_outflow: Decimal
    projected_balance: Decimal

class CashForecastResult(BaseModel):
    weeks: list[WeekProjection]
    zero_cash_week: int | None

class FinancialSummary(BaseModel):
    current_cash_balance: Decimal
    monthly_financials: list[MonthlyFinancial]

class Anomaly(BaseModel):
    category: str
    current_amount: Decimal
    historical_mean: Decimal
    z_score: Decimal
    severity: Literal["warning", "critical"]
    description: str

class AnomalyResult(BaseModel):
    anomalies: list[Anomaly]
    scan_period_months: int

class ScenarioChange(BaseModel):
    type: Literal["hire", "fire", "revenue_change", "new_expense", "cut_expense"]
    description: str
    monthly_impact: Decimal = Decimal("0")
    pct_of_burn: Decimal | None = None   # signed fraction vs baseline net burn; -0.20 = 20% cut
    pct_of_expenses: Decimal | None = None   # signed fraction vs baseline gross burn (expenses); -0.20 = 20% expense cut

class ScenarioResult(BaseModel):
    current_runway: Decimal
    new_runway: Decimal
    delta_runway: Decimal
    current_burn: Decimal
    new_burn: Decimal
    delta_burn: Decimal
    changes_applied: list[ScenarioChange]

class FundraisingMetrics(BaseModel):
    mrr: Decimal | None
    mrr_growth_rate: Decimal | None
    arr: Decimal | None
    burn_multiple: Decimal | None
    runway_months: Decimal
    gross_margin: Decimal | None

class FundraisingResult(BaseModel):
    readiness_score: int
    metrics: FundraisingMetrics
    gaps: list[str]

class RunRateMonth(BaseModel):
    month_start: date
    total_revenue: Decimal

class RunRateResult(BaseModel):
    run_rate: Decimal | None
    months_used: list[RunRateMonth]
    month_count: int
    low_confidence: bool
    is_volatile: bool
    volatility_ratio: Decimal
    min_revenue: Decimal
    max_revenue: Decimal
    caveat: str

