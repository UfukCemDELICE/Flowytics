import pytest
from datetime import date
from decimal import Decimal
from backend.app.tools.burn_rate import calculate_burn_rate
from backend.app.tools.runway import calculate_runway
from backend.app.tools.cash_forecast import calculate_cash_forecast
from backend.app.tools.financial_summary import parse_qbo_to_financial_summary
from backend.app.tools.schemas import FinancialSummary, MonthlyFinancial, BurnRateResult

def test_financial_summary_parsing():
    pl_data = {
        "monthly_data": [
            {"month": "2025-01", "revenue": "1000", "expenses": "500", "net_income": "500"}
        ]
    }
    bs_data = {"current_cash_balance": "1500"}
    summary = parse_qbo_to_financial_summary.invoke({"pl_data": pl_data, "bs_data": bs_data})
    assert len(summary.monthly_financials) == 1
    assert summary.current_cash_balance == Decimal("1500")
    assert summary.monthly_financials[0].net_income == Decimal("500")

    empty_summary = parse_qbo_to_financial_summary.invoke({"pl_data": {}, "bs_data": {}})
    assert empty_summary.current_cash_balance == Decimal("0")
    assert len(empty_summary.monthly_financials) == 0

def test_burn_rate_edge_cases():
    empty_summary = FinancialSummary(current_cash_balance=Decimal("0"), monthly_financials=[])
    res1 = calculate_burn_rate.invoke({"summary": empty_summary})
    assert res1.net_burn_monthly == Decimal("0")
    
    single_month = FinancialSummary(
        current_cash_balance=Decimal("100"),
        monthly_financials=[
            MonthlyFinancial(month_start=date(2025,1,1), total_revenue=Decimal("0"), total_expenses=Decimal("10"), net_income=Decimal("-10"))
        ]
    )
    res2 = calculate_burn_rate.invoke({"summary": single_month})
    assert res2.trend_slope == Decimal("0")

def test_runway_edge_cases():
    summary = FinancialSummary(current_cash_balance=Decimal("50000"), monthly_financials=[])
    
    burn_warning = BurnRateResult(net_burn_monthly=Decimal("10000"), gross_burn_monthly=Decimal("10000"), burn_multiple=None, trend="stable", trend_slope=Decimal("0"), period_months=3)
    res_warn = calculate_runway.invoke({"summary": summary, "burn_rate": burn_warning})
    assert res_warn.runway_status == "warning"

    burn_monitor = BurnRateResult(net_burn_monthly=Decimal("5000"), gross_burn_monthly=Decimal("5000"), burn_multiple=None, trend="stable", trend_slope=Decimal("0"), period_months=3)
    res_monitor = calculate_runway.invoke({"summary": summary, "burn_rate": burn_monitor})
    assert res_monitor.runway_status == "monitor"

    burn_infinity = BurnRateResult(net_burn_monthly=Decimal("0.0000001"), gross_burn_monthly=Decimal("0"), burn_multiple=None, trend="stable", trend_slope=Decimal("0"), period_months=3)
    res_overflow = calculate_runway.invoke({"summary": summary, "burn_rate": burn_infinity})
    assert res_overflow.cash_zero_date is None

def test_cash_forecast_empty():
    empty_summary = FinancialSummary(current_cash_balance=Decimal("0"), monthly_financials=[])
    res = calculate_cash_forecast.invoke({"summary": empty_summary})
    assert len(res.weeks) == 0
    assert res.zero_cash_week is None
