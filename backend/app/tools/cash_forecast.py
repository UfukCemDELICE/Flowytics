from datetime import date, timedelta
from decimal import Decimal
from langchain_core.tools import tool
from backend.app.tools.schemas import FinancialSummary, CashForecastResult, WeekProjection

from backend.app.utils import clean_unicode_minus

@tool
def calculate_cash_forecast(summary: FinancialSummary) -> CashForecastResult:
    """
    Calculates a 13-week cash projection. 
    In the absence of weekly raw data, we extrapolate trends from the monthly financials.
    """
    financials = sorted(summary.monthly_financials, key=lambda x: x.month_start)
    if not financials:
        # Provide flat zero forecast if no data
        return clean_unicode_minus(CashForecastResult(weeks=[], zero_cash_week=None))

    # Use the last 3 months to configure a baseline weekly rate
    recent = financials[-3:] if len(financials) >= 3 else financials
    recent_count = Decimal(str(len(recent)))
    
    avg_monthly_inflow = sum((d.total_revenue for d in recent), start=Decimal("0")) / recent_count
    avg_monthly_outflow = sum((d.total_expenses for d in recent), start=Decimal("0")) / recent_count

    # Convert to weekly base (avg ~4.33 weeks per month)
    weeks_per_month = Decimal("4.33")
    base_weekly_inflow = avg_monthly_inflow / weeks_per_month
    base_weekly_outflow = avg_monthly_outflow / weeks_per_month

    # For trend, we can just use the flat base for the MVP 13-week projection.
    # Advanced: calculate weekly growth rates. We will stick to flat for reliability in this sprint.
    weeks = []
    current_balance = summary.current_cash_balance
    zero_cash_week = None
    
    current_date = date.today()

    for i in range(13):
        projected_inflow = base_weekly_inflow.quantize(Decimal("0.01"))
        projected_outflow = base_weekly_outflow.quantize(Decimal("0.01"))
        
        current_balance = current_balance + projected_inflow - projected_outflow
        current_balance = current_balance.quantize(Decimal("0.01"))

        if current_balance < 0 and zero_cash_week is None:
            zero_cash_week = i + 1

        weeks.append(WeekProjection(
            week_start=current_date,
            projected_inflow=projected_inflow,
            projected_outflow=projected_outflow,
            projected_balance=current_balance
        ))
        
        current_date += timedelta(days=7)

    return clean_unicode_minus(CashForecastResult(
        weeks=weeks,
        zero_cash_week=zero_cash_week
    ))
