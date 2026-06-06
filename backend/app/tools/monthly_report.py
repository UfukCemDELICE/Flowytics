from langchain_core.tools import tool
from pydantic import BaseModel

from backend.app.tools.schemas import (
    FinancialSummary, 
    BurnRateResult, 
    RunwayResult, 
    CashForecastResult,
    AnomalyResult,
    FundraisingResult
)
from backend.app.tools.burn_rate import calculate_burn_rate
from backend.app.tools.runway import calculate_runway
from backend.app.tools.cash_forecast import calculate_cash_forecast
from backend.app.tools.anomaly import calculate_anomalies
from backend.app.tools.fundraising import calculate_fundraising_readiness

class MonthlyReportData(BaseModel):
    """Structured deterministic mathematical container for the end of month CFO report."""
    raw_summary: FinancialSummary
    burn: BurnRateResult
    runway: RunwayResult
    forecast: CashForecastResult
    anomalies: AnomalyResult
    fundraising: FundraisingResult

from backend.app.utils import clean_unicode_minus

@tool
def generate_monthly_report_data(summary: FinancialSummary) -> MonthlyReportData:
    """
    Aggregates a complete deterministic dataset of the startup's current financial posture.
    Invokes burn rate, runway, anomaly checking, and fundraising math tools.
    """
    burn = calculate_burn_rate.invoke({"summary": summary})
    runway = calculate_runway.invoke({"summary": summary, "burn_rate": burn})
    forecast = calculate_cash_forecast.invoke({"summary": summary, "runway": runway})
    anomalies = calculate_anomalies.invoke({"summary": summary})
    fundraising = calculate_fundraising_readiness.invoke({"summary": summary})
    
    return clean_unicode_minus(MonthlyReportData(
        raw_summary=summary,
        burn=burn,
        runway=runway,
        forecast=forecast,
        anomalies=anomalies,
        fundraising=fundraising
    ))
