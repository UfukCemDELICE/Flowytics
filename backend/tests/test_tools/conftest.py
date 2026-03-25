from datetime import date
from decimal import Decimal
import pytest
from backend.app.tools.schemas import MonthlyFinancial, FinancialSummary

@pytest.fixture
def profile_healthy():
    return FinancialSummary(
        current_cash_balance=Decimal("500000"),
        monthly_financials=[
            MonthlyFinancial(month_start=date(2025, 1, 1), total_revenue=Decimal("10000"), total_expenses=Decimal("20000"), net_income=Decimal("-10000")),
            MonthlyFinancial(month_start=date(2025, 2, 1), total_revenue=Decimal("12000"), total_expenses=Decimal("21000"), net_income=Decimal("-9000")),
            MonthlyFinancial(month_start=date(2025, 3, 1), total_revenue=Decimal("15000"), total_expenses=Decimal("22000"), net_income=Decimal("-7000")),
            MonthlyFinancial(month_start=date(2025, 4, 1), total_revenue=Decimal("18000"), total_expenses=Decimal("21000"), net_income=Decimal("-3000")),
            MonthlyFinancial(month_start=date(2025, 5, 1), total_revenue=Decimal("20000"), total_expenses=Decimal("22000"), net_income=Decimal("-2000")),
            MonthlyFinancial(month_start=date(2025, 6, 1), total_revenue=Decimal("22000"), total_expenses=Decimal("23000"), net_income=Decimal("-1000")),
        ]
    )

@pytest.fixture
def profile_pre_revenue():
    return FinancialSummary(
        current_cash_balance=Decimal("200000"),
        monthly_financials=[
            MonthlyFinancial(month_start=date(2025, 1, 1), total_revenue=Decimal("0"), total_expenses=Decimal("30000"), net_income=Decimal("-30000")),
            MonthlyFinancial(month_start=date(2025, 2, 1), total_revenue=Decimal("0"), total_expenses=Decimal("35000"), net_income=Decimal("-35000")),
            MonthlyFinancial(month_start=date(2025, 3, 1), total_revenue=Decimal("0"), total_expenses=Decimal("35000"), net_income=Decimal("-35000")),
            MonthlyFinancial(month_start=date(2025, 4, 1), total_revenue=Decimal("0"), total_expenses=Decimal("40000"), net_income=Decimal("-40000")),
            MonthlyFinancial(month_start=date(2025, 5, 1), total_revenue=Decimal("0"), total_expenses=Decimal("40000"), net_income=Decimal("-40000")),
            MonthlyFinancial(month_start=date(2025, 6, 1), total_revenue=Decimal("0"), total_expenses=Decimal("45000"), net_income=Decimal("-45000")),
        ]
    )

@pytest.fixture
def profile_dying():
    return FinancialSummary(
        current_cash_balance=Decimal("40000"),
        monthly_financials=[
            MonthlyFinancial(month_start=date(2025, 1, 1), total_revenue=Decimal("5000"), total_expenses=Decimal("50000"), net_income=Decimal("-45000")),
            MonthlyFinancial(month_start=date(2025, 2, 1), total_revenue=Decimal("4500"), total_expenses=Decimal("55000"), net_income=Decimal("-50500")),
            MonthlyFinancial(month_start=date(2025, 3, 1), total_revenue=Decimal("4000"), total_expenses=Decimal("60000"), net_income=Decimal("-56000")),
        ]
    )

@pytest.fixture
def profile_profitable():
    return FinancialSummary(
        current_cash_balance=Decimal("1000000"),
        monthly_financials=[
            MonthlyFinancial(month_start=date(2025, 1, 1), total_revenue=Decimal("80000"), total_expenses=Decimal("60000"), net_income=Decimal("20000")),
            MonthlyFinancial(month_start=date(2025, 2, 1), total_revenue=Decimal("85000"), total_expenses=Decimal("62000"), net_income=Decimal("23000")),
            MonthlyFinancial(month_start=date(2025, 3, 1), total_revenue=Decimal("90000"), total_expenses=Decimal("65000"), net_income=Decimal("25000")),
        ]
    )

@pytest.fixture
def profile_new():
    return FinancialSummary(
        current_cash_balance=Decimal("750000"),
        monthly_financials=[
            MonthlyFinancial(month_start=date(2025, 5, 1), total_revenue=Decimal("0"), total_expenses=Decimal("10000"), net_income=Decimal("-10000")),
            MonthlyFinancial(month_start=date(2025, 6, 1), total_revenue=Decimal("0"), total_expenses=Decimal("15000"), net_income=Decimal("-15000")),
        ]
    )
