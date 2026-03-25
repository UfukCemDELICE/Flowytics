from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

class MonthlyFinancial(BaseModel):
    month_start: date
    total_revenue: Decimal
    total_expenses: Decimal
    net_income: Decimal

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
