from datetime import date, datetime
from decimal import Decimal
from typing import Literal, TypedDict

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Financial data models
# ---------------------------------------------------------------------------

class FinancialRow(BaseModel):
    category: str
    subcategory: str
    amount: Decimal
    period: str  # e.g. "2025-01"


class FinancialStatement(BaseModel):
    statement_type: Literal["profit_loss", "balance_sheet", "cash_flow"]
    company_name: str
    currency: str
    period_start: date
    period_end: date
    rows: list[FinancialRow]


# ---------------------------------------------------------------------------
# Tool input/output models
# ---------------------------------------------------------------------------

class RatioInput(BaseModel):
    statements: list[FinancialStatement]
    headcount: int | None = None


class RatioResult(BaseModel):
    gross_margin: Decimal | None
    net_margin: Decimal | None
    operating_margin: Decimal | None
    current_ratio: Decimal | None
    quick_ratio: Decimal | None
    debt_to_equity: Decimal | None
    mom_revenue_growth: Decimal | None
    yoy_revenue_growth: Decimal | None
    revenue_per_employee: Decimal | None
    arr: Decimal | None
    mrr: Decimal | None
    net_revenue_retention: Decimal | None
    period: str


class RunwayInput(BaseModel):
    cash_flow_statement: FinancialStatement
    current_cash: Decimal


class RunwayAlert(BaseModel):
    level: Literal["CRITICAL", "WARNING", "INFO", "OK"]
    message: str


class RunwayResult(BaseModel):
    monthly_burn_rate: Decimal
    runway_months: Decimal | None
    weighted_burn_rate: Decimal
    burn_trend: Literal["increasing", "stable", "decreasing"]
    cash_zero_date: date | None
    alert: RunwayAlert


class BudgetCategory(BaseModel):
    category: str
    actual: Decimal
    budget: Decimal
    variance_pct: Decimal
    mom_growth: Decimal | None
    expense_to_revenue_pct: Decimal | None
    alert: Literal["CRITICAL", "WARNING", "OK"]


class BudgetInput(BaseModel):
    statements: list[FinancialStatement]
    budget_targets: dict[str, Decimal] | None = None


class BudgetResult(BaseModel):
    categories: list[BudgetCategory]
    top5_by_spend: list[str]
    total_expense_mom_growth: Decimal | None
    alerts: list[str]


class AnomalyItem(BaseModel):
    category: str
    period: str
    value: Decimal
    z_score: Decimal
    severity: Literal["HIGH", "MEDIUM", "LOW"]
    reason: str


class AnomalyInput(BaseModel):
    statements: list[FinancialStatement]


class AnomalyResult(BaseModel):
    anomalies: list[AnomalyItem]


class ValidationDiscrepancy(BaseModel):
    field: str
    tool_value: Decimal
    llm_value: Decimal
    discrepancy_pct: Decimal
    severity: Literal["ERROR", "WARNING"]


class ValidatorResult(BaseModel):
    discrepancies: list[ValidationDiscrepancy]
    is_clean: bool


# ---------------------------------------------------------------------------
# QuickBooks token storage model
# ---------------------------------------------------------------------------

class QBTokenRecord(BaseModel):
    user_id: str
    realm_id: str
    access_token: str
    refresh_token: str
    expires_at: datetime


# ---------------------------------------------------------------------------
# Slack mapping model
# ---------------------------------------------------------------------------

class SlackUserMap(BaseModel):
    clerk_user_id: str
    slack_user_id: str
    slack_team_id: str


# ---------------------------------------------------------------------------
# LangGraph agent state
# ---------------------------------------------------------------------------

class AgentState(TypedDict):
    user_id: str
    request_type: Literal["report", "cashflow", "expense", "slack"]
    request_params: dict
    financial_data: dict | None
    cache_hit: bool
    tool_results: dict
    model_used: str
    llm_analysis: str
    llm_numbers: dict
    discrepancies: list[dict]
    output: dict


# ---------------------------------------------------------------------------
# API response models
# ---------------------------------------------------------------------------

class ReportResponse(BaseModel):
    user_id: str
    report_type: str
    ratios: RatioResult | None = None
    runway: RunwayResult | None = None
    budget: BudgetResult | None = None
    anomalies: AnomalyResult | None = None
    analysis: str = ""
    model_used: str = ""
    discrepancies: list[dict] = []
    generated_at: datetime


class RunwayResponse(BaseModel):
    user_id: str
    runway: RunwayResult
    forecast_months: int
    analysis: str
    model_used: str
    generated_at: datetime


class ExpenseResponse(BaseModel):
    user_id: str
    budget: BudgetResult
    anomalies: AnomalyResult
    summary: str
    model_used: str
    generated_at: datetime
