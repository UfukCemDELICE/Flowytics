from datetime import date
from decimal import Decimal
from backend.app.tools.run_rate import calculate_run_rate
from backend.app.tools.schemas import FinancialSummary, MonthlyFinancial

def test_run_rate_three_months_volatile():
    # Case 1: Three months [1018.00, 4054.14, 4372.38]
    summary = FinancialSummary(
        current_cash_balance=Decimal("50000"),
        monthly_financials=[
            MonthlyFinancial(
                month_start=date(2025, 1, 1),
                total_revenue=Decimal("1018.00"),
                total_expenses=Decimal("5000"),
                net_income=Decimal("-3982.00")
            ),
            MonthlyFinancial(
                month_start=date(2025, 2, 1),
                total_revenue=Decimal("4054.14"),
                total_expenses=Decimal("5000"),
                net_income=Decimal("-945.86")
            ),
            MonthlyFinancial(
                month_start=date(2025, 3, 1),
                total_revenue=Decimal("4372.38"),
                total_expenses=Decimal("5000"),
                net_income=Decimal("-627.62")
            ),
        ]
    )
    result = calculate_run_rate.invoke({"summary": summary})
    
    # Assert exact run rate
    assert result.run_rate == Decimal("37778.08")
    assert isinstance(result.run_rate, Decimal)
    
    # Assert volatility
    assert result.is_volatile is True
    # volatility_ratio = (4372.38 - 1018.00) / ((1018.00 + 4054.14 + 4372.38) / 3)
    # Average = 3148.173333333333333333333333
    # Ratio = 3354.38 / 3148.173333333333333333333333 = 1.065500416390196887532320701
    assert abs(result.volatility_ratio - Decimal("1.0655")) < Decimal("0.001")
    assert isinstance(result.volatility_ratio, Decimal)
    assert isinstance(result.min_revenue, Decimal)
    assert isinstance(result.max_revenue, Decimal)
    
    # Assert caveat contains volatility details
    assert "Note: monthly revenue varied significantly (low: $1,018.00, high: $4,372.38)" in result.caveat
    assert "This is an annualized run rate based on your last 3 month(s) of revenue, not true ARR." in result.caveat

def test_run_rate_one_month_only():
    # Case 2: One month only
    summary = FinancialSummary(
        current_cash_balance=Decimal("50000"),
        monthly_financials=[
            MonthlyFinancial(
                month_start=date(2025, 1, 1),
                total_revenue=Decimal("2000.00"),
                total_expenses=Decimal("1500"),
                net_income=Decimal("500")
            )
        ]
    )
    result = calculate_run_rate.invoke({"summary": summary})
    
    # Expected run rate = 2000 * 12 = 24000
    assert result.run_rate == Decimal("24000.00")
    assert result.month_count == 1
    assert result.low_confidence is True
    assert result.is_volatile is False # only 1 month, so max_rev - min_rev == 0
    assert result.volatility_ratio == Decimal("0")
    assert "This is an annualized run rate based on your last 1 month(s) of revenue, not true ARR." in result.caveat

def test_run_rate_zero_months():
    # Case 3: Zero months
    summary = FinancialSummary(
        current_cash_balance=Decimal("50000"),
        monthly_financials=[]
    )
    result = calculate_run_rate.invoke({"summary": summary})
    
    assert result.run_rate is None
    assert result.month_count == 0
    assert result.low_confidence is True
    assert "No revenue data is available" in result.caveat
    # Ensure no float values are present in fields
    assert isinstance(result.volatility_ratio, Decimal)
    assert isinstance(result.min_revenue, Decimal)
    assert isinstance(result.max_revenue, Decimal)
