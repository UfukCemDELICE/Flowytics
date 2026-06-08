from datetime import date
from decimal import Decimal
import pytest

from backend.app.tools.burn_rate import calculate_burn_rate
from backend.app.tools.run_rate import calculate_run_rate
from backend.app.tools.cash_forecast import calculate_cash_forecast
from backend.app.tools.anomaly import calculate_anomalies
from backend.app.tools.fundraising import calculate_fundraising_readiness
from backend.app.tools.schemas import FinancialSummary, MonthlyFinancial

def test_burn_rate_sprint8_leading_zeros():
    # Month 1 & 2 are leading zeros
    summary = FinancialSummary(
        current_cash_balance=Decimal("100000"),
        monthly_financials=[
            MonthlyFinancial(month_start=date(2025, 1, 1), total_revenue=Decimal("0"), total_expenses=Decimal("1000"), net_income=Decimal("-1000")),
            MonthlyFinancial(month_start=date(2025, 2, 1), total_revenue=Decimal("0"), total_expenses=Decimal("2000"), net_income=Decimal("-2000")),
            MonthlyFinancial(month_start=date(2025, 3, 1), total_revenue=Decimal("5000"), total_expenses=Decimal("8000"), net_income=Decimal("-3000")),
            MonthlyFinancial(month_start=date(2025, 4, 1), total_revenue=Decimal("6000"), total_expenses=Decimal("9000"), net_income=Decimal("-3000")),
            MonthlyFinancial(month_start=date(2025, 5, 1), total_revenue=Decimal("7000"), total_expenses=Decimal("10000"), net_income=Decimal("-3000")),
        ]
    )
    
    result = calculate_burn_rate.invoke({"summary": summary})
    
    # Assertions
    # 1. period_months should be 3 (since leading zeros are excluded, leaving 3 months)
    assert result.period_months == 3
    # 2. net_burn_monthly should be average of the 3 active months: 3000
    assert result.net_burn_monthly == Decimal("3000")
    # 3. gross_burn_monthly should be average of the 3 active months: (8000+9000+10000)/3 = 9000
    assert result.gross_burn_monthly == Decimal("9000")
    # 4. burn_multiple: total_net_burn = abs(-9000) = 9000
    #    net_new_ARR = (7000 * 12) - (5000 * 12) = 24000
    #    burn_multiple = 9000 / 24000 = 0.38
    assert result.burn_multiple == Decimal("0.38")


def test_burn_rate_sprint8_partial_month_guard():
    today = date.today()
    curr_yr, curr_mo = today.year, today.month
    
    # Helper to build dates in the past
    def past_month(offset: int) -> date:
        # returns the start date of a month offset months ago
        yr = curr_yr
        mo = curr_mo - offset
        while mo <= 0:
            mo += 12
            yr -= 1
        return date(yr, mo, 1)
        
    summary = FinancialSummary(
        current_cash_balance=Decimal("100000"),
        monthly_financials=[
            MonthlyFinancial(month_start=past_month(3), total_revenue=Decimal("1000"), total_expenses=Decimal("4000"), net_income=Decimal("-3000")),
            MonthlyFinancial(month_start=past_month(2), total_revenue=Decimal("2000"), total_expenses=Decimal("5000"), net_income=Decimal("-3000")),
            MonthlyFinancial(month_start=past_month(1), total_revenue=Decimal("3000"), total_expenses=Decimal("6000"), net_income=Decimal("-3000")),
            # The current partial month has activity, but MUST be excluded
            MonthlyFinancial(month_start=date(curr_yr, curr_mo, 1), total_revenue=Decimal("10000"), total_expenses=Decimal("12000"), net_income=Decimal("-2000")),
        ]
    )
    
    # 1. Burn Rate
    burn_res = calculate_burn_rate.invoke({"summary": summary})
    assert burn_res.period_months == 3
    # it must average over the 3 full months: past_month(3), (2), (1)
    assert burn_res.net_burn_monthly == Decimal("3000")
    
    # 2. Run Rate
    rr_res = calculate_run_rate.invoke({"summary": summary})
    # it must use the 3 full months (max rev is 3000, not 10000)
    assert rr_res.max_revenue == Decimal("3000")
    
    # 3. Cash Forecast
    forecast_res = calculate_cash_forecast.invoke({"summary": summary})
    # average monthly revenue of 3 full months is (1000+2000+3000)/3 = 2000
    # weekly inflow is 2000 / 4.33 ≈ 461.89
    assert forecast_res.weeks[0].projected_inflow == Decimal("461.89")
    
    # 4. Anomalies
    # If the target was the current month (with expenses = 12000), it might trigger anomalies.
    # But it must use past_month(1) as target. Since past_month(1) expenses are 6000 (AWS/etc not spiked),
    # there should be no anomalies.
    # Let's add categories to verify
    summary_with_cats = FinancialSummary(
        current_cash_balance=Decimal("100000"),
        monthly_financials=[
            MonthlyFinancial(month_start=past_month(3), total_revenue=Decimal("1000"), total_expenses=Decimal("4000"), net_income=Decimal("-3000"), category_expenses={"AWS": Decimal("500")}),
            MonthlyFinancial(month_start=past_month(2), total_revenue=Decimal("2000"), total_expenses=Decimal("5000"), net_income=Decimal("-3000"), category_expenses={"AWS": Decimal("500")}),
            MonthlyFinancial(month_start=past_month(1), total_revenue=Decimal("3000"), total_expenses=Decimal("6000"), net_income=Decimal("-3000"), category_expenses={"AWS": Decimal("500")}),
            MonthlyFinancial(month_start=date(curr_yr, curr_mo, 1), total_revenue=Decimal("10000"), total_expenses=Decimal("12000"), net_income=Decimal("-2000"), category_expenses={"AWS": Decimal("10000")}), # huge spike in partial current month
        ]
    )
    anomaly_res = calculate_anomalies.invoke({"summary": summary_with_cats})
    # The current month AWS spike must be ignored, so 0 anomalies detected
    assert len(anomaly_res.anomalies) == 0
    
    # 5. Fundraising
    fund_res = calculate_fundraising_readiness.invoke({"summary": summary})
    # MRR should be from past_month(1), which is 3000 (not 10000)
    assert fund_res.metrics.mrr == Decimal("3000")


def test_fundraising_gross_margin_calculation():
    # Test Gross Margin logic
    summary = FinancialSummary(
        current_cash_balance=Decimal("100000"),
        monthly_financials=[
            MonthlyFinancial(month_start=date(2025, 1, 1), total_revenue=Decimal("10000"), total_expenses=Decimal("5000"), net_income=Decimal("5000"), total_cogs=Decimal("3000")),
            MonthlyFinancial(month_start=date(2025, 2, 1), total_revenue=Decimal("12000"), total_expenses=Decimal("6000"), net_income=Decimal("6000"), total_cogs=Decimal("3600")),
            MonthlyFinancial(month_start=date(2025, 3, 1), total_revenue=Decimal("15000"), total_expenses=Decimal("7000"), net_income=Decimal("8000"), total_cogs=Decimal("4500")),
        ]
    )
    
    # 1. Verify COGS field exists on the MonthlyFinancial
    assert summary.monthly_financials[0].total_cogs == Decimal("3000")
    
    # 2. Verify fundraising readiness calculates real gross margin
    # total_rev_3m = 10000 + 12000 + 15000 = 37000
    # total_cogs_3m = 3000 + 3600 + 4500 = 11100
    # gross_margin = (37000 - 11100) / 37000 * 100 = 70.00%
    result = calculate_fundraising_readiness.invoke({"summary": summary})
    assert result.metrics.gross_margin == Decimal("70.00")
    
    # Test when revenue is zero
    summary_zero = FinancialSummary(
        current_cash_balance=Decimal("100000"),
        monthly_financials=[
            MonthlyFinancial(month_start=date(2025, 1, 1), total_revenue=Decimal("0"), total_expenses=Decimal("1000"), net_income=Decimal("-1000")),
        ]
    )
    res_zero = calculate_fundraising_readiness.invoke({"summary": summary_zero})
    assert res_zero.metrics.gross_margin is None

