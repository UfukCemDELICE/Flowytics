from decimal import Decimal
from backend.app.tools.burn_rate import calculate_burn_rate
from backend.app.tools.runway import calculate_runway
from backend.app.tools.cash_forecast import calculate_cash_forecast

def test_burn_rate_healthy(profile_healthy):
    result = calculate_burn_rate.invoke({"summary": profile_healthy})
    assert result.trend in ["decreasing", "stable"]
    assert result.net_burn_monthly > Decimal("0")
    assert result.period_months == 6

def test_burn_rate_dying(profile_dying):
    result = calculate_burn_rate.invoke({"summary": profile_dying})
    assert result.trend == "increasing"
    assert result.net_burn_monthly > Decimal("45000")
    assert result.period_months == 3

def test_runway_healthy(profile_healthy):
    burn = calculate_burn_rate.invoke({"summary": profile_healthy})
    runway = calculate_runway.invoke({"summary": profile_healthy, "burn_rate": burn})
    assert runway.runway_status == "healthy"
    assert runway.runway_months > Decimal("12")

def test_runway_dying(profile_dying):
    burn = calculate_burn_rate.invoke({"summary": profile_dying})
    runway = calculate_runway.invoke({"summary": profile_dying, "burn_rate": burn})
    assert runway.runway_status == "critical"
    assert runway.runway_months < Decimal("3")

def test_runway_profitable(profile_profitable):
    burn = calculate_burn_rate.invoke({"summary": profile_profitable})
    runway = calculate_runway.invoke({"summary": profile_profitable, "burn_rate": burn})
    assert runway.runway_status == "healthy"
    assert runway.runway_months == Decimal("9999")
    
def test_cash_forecast(profile_healthy):
    forecast = calculate_cash_forecast.invoke({"summary": profile_healthy})
    assert len(forecast.weeks) == 13
    assert forecast.weeks[0].projected_inflow > Decimal("0")
    assert forecast.zero_cash_week is None

def test_cash_forecast_dying(profile_dying):
    forecast = calculate_cash_forecast.invoke({"summary": profile_dying})
    assert forecast.zero_cash_week is not None
    assert forecast.zero_cash_week <= 5

def test_qbo_parser_sandbox_values():
    from datetime import date
    from backend.app.tools.qbo_parser import parse_financial_summary

    pl_data = {
        "Rows": {
            "Row": [
                {
                    "group": "Income",
                    "Summary": {"ColData": [{}, {"value": "10200.77"}]}
                },
                {
                    "group": "Expenses",
                    "Summary": {"ColData": [{}, {"value": "5642.31"}]}
                },
                {
                    "group": "OtherExpenses",
                    "Summary": {"ColData": [{}, {"value": "2916.00"}]}
                },
                {
                    "group": "NetIncome",
                    "Summary": {"ColData": [{}, {"value": "1642.46"}]}
                }
            ]
        }
    }
    bs_data = {"Rows": {"Row": []}}
    
    summary = parse_financial_summary(pl_data, bs_data, date(2026, 6, 5))
    monthly = summary.monthly_financials[0]
    
    assert monthly.total_revenue == Decimal("10200.77")
    assert monthly.total_expenses == Decimal("8558.31")
    assert monthly.net_income == Decimal("1642.46")
    assert monthly.total_revenue - monthly.total_expenses == monthly.net_income
