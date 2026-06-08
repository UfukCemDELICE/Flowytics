from decimal import Decimal
from datetime import date
from backend.app.tools.schemas import FinancialSummary, MonthlyFinancial
from backend.app.tools.anomaly import calculate_anomalies
from backend.app.tools.fundraising import calculate_fundraising_readiness
from backend.app.tools.monthly_report import generate_monthly_report_data

def test_anomaly_insufficient_category_history():
    """Test line 33 in anomaly.py (len(hist_amounts) < 2)"""
    summary = FinancialSummary(
        current_cash_balance=Decimal("10000"),
        monthly_financials=[
            MonthlyFinancial(month_start=date(2025, 1, 1), total_revenue=Decimal("0"), total_expenses=Decimal("0"), net_income=Decimal("0"), category_expenses={"Marketing": Decimal("100")}),
            MonthlyFinancial(month_start=date(2025, 2, 1), total_revenue=Decimal("0"), total_expenses=Decimal("0"), net_income=Decimal("0"), category_expenses={"Software": Decimal("100")}),
            MonthlyFinancial(month_start=date(2025, 3, 1), total_revenue=Decimal("0"), total_expenses=Decimal("0"), net_income=Decimal("0"), category_expenses={"Software": Decimal("100"), "NewCat": Decimal("500")}),
        ]
    )
    result = calculate_anomalies.invoke({"summary": summary})
    assert result.scan_period_months == 1
    assert len(result.anomalies) == 0

def test_fundraising_empty_financials():
    """Test line 15 in fundraising.py (if not financials)"""
    summary = FinancialSummary(
        current_cash_balance=Decimal("10000"),
        monthly_financials=[]
    )
    result = calculate_fundraising_readiness.invoke({"summary": summary})
    assert result.readiness_score == 0
    assert "No financial history found." in result.gaps

def test_fundraising_high_growth_rate():
    """Test line 60 in fundraising.py (mrr_growth_rate >= 15)"""
    summary = FinancialSummary(
        current_cash_balance=Decimal("50000"),
        monthly_financials=[
            MonthlyFinancial(
                month_start=date(2024, 1, 1), 
                total_revenue=Decimal("10000"), 
                total_expenses=Decimal("12000"),
                net_income=Decimal("-2000"),
                category_expenses={}
            ),
            MonthlyFinancial(
                month_start=date(2024, 2, 1), 
                total_revenue=Decimal("12000"), # 20% growth
                total_expenses=Decimal("14000"),
                net_income=Decimal("-2000"),
                category_expenses={}
            ),
        ]
    )
    
    result = calculate_fundraising_readiness.invoke({"summary": summary})    # High growth (20%) -> line 60 path hit
    assert result.metrics.mrr_growth_rate == Decimal("20.00")

    # It should pass the growth threshold check and potentially others depending on runway

def test_monthly_report_execution():
    """Test monthly report aggregation returns a populated dict/model."""
    from backend.app.tools.schemas import MonthlyFinancial, FinancialSummary
    
    summary = FinancialSummary(
        current_cash_balance=Decimal("100000"),
        monthly_financials=[
            MonthlyFinancial(month_start=date(2025, 1, 1), total_revenue=Decimal("10000"), total_expenses=Decimal("8000"), net_income=Decimal("2000")),
            MonthlyFinancial(month_start=date(2025, 2, 1), total_revenue=Decimal("12000"), total_expenses=Decimal("9000"), net_income=Decimal("3000"))
        ]
    )
    
    res = generate_monthly_report_data.invoke({"summary": summary})
    assert res.runway.cash_balance == Decimal("100000")
    assert res.fundraising.metrics.mrr == Decimal("12000")
