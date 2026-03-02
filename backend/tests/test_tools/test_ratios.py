"""
Tests for tools/ratios.py — deterministic financial ratio calculations.
Uses known financial data with expected outputs verified by hand.
"""
from datetime import date
from decimal import Decimal

import pytest

from backend.app.models.schemas import FinancialRow, FinancialStatement, RatioInput
from backend.app.tools.ratios import calculate_ratios


def _make_pl(rows: list[tuple[str, str, str, str]]) -> FinancialStatement:
    """Helper: build a profit_loss FinancialStatement from (cat, subcat, amount, period) tuples."""
    return FinancialStatement(
        statement_type="profit_loss",
        company_name="TestCo",
        currency="USD",
        period_start=date(2024, 1, 1),
        period_end=date(2024, 12, 31),
        rows=[
            FinancialRow(category=r[0], subcategory=r[1], amount=Decimal(r[2]), period=r[3])
            for r in rows
        ],
    )


def _make_bs(rows: list[tuple[str, str, str, str]]) -> FinancialStatement:
    return FinancialStatement(
        statement_type="balance_sheet",
        company_name="TestCo",
        currency="USD",
        period_start=date(2024, 1, 1),
        period_end=date(2024, 12, 31),
        rows=[
            FinancialRow(category=r[0], subcategory=r[1], amount=Decimal(r[2]), period=r[3])
            for r in rows
        ],
    )


class TestGrossMargin:
    def test_basic_gross_margin(self):
        """Gross margin = (Revenue - COGS) / Revenue"""
        pl = _make_pl([
            ("Revenue", "Sales", "100000", "2024-12"),
            ("Cost of Goods Sold", "Direct", "40000", "2024-12"),
        ])
        result = calculate_ratios(RatioInput(statements=[pl]))
        assert result.gross_margin == Decimal("0.60")

    def test_zero_revenue(self):
        """Zero revenue → gross margin is None (avoids division by zero)."""
        pl = _make_pl([
            ("Revenue", "Sales", "0", "2024-12"),
            ("Cost of Goods Sold", "Direct", "10000", "2024-12"),
        ])
        result = calculate_ratios(RatioInput(statements=[pl]))
        assert result.gross_margin is None

    def test_100_percent_margin(self):
        """Pure software — no COGS → 100% gross margin."""
        pl = _make_pl([
            ("Revenue", "SaaS", "50000", "2024-12"),
        ])
        result = calculate_ratios(RatioInput(statements=[pl]))
        assert result.gross_margin == Decimal("1")


class TestNetMargin:
    def test_profitable_company(self):
        """Net margin = Net Income / Revenue"""
        pl = _make_pl([
            ("Revenue", "Sales", "200000", "2024-12"),
            ("Net Income", "Total", "30000", "2024-12"),
        ])
        result = calculate_ratios(RatioInput(statements=[pl]))
        assert result.net_margin == Decimal("0.15")

    def test_unprofitable_company(self):
        """Negative net income → negative margin."""
        pl = _make_pl([
            ("Revenue", "Sales", "100000", "2024-12"),
            ("Net Income", "Total", "-20000", "2024-12"),
        ])
        result = calculate_ratios(RatioInput(statements=[pl]))
        assert result.net_margin == Decimal("-0.20")


class TestCurrentRatio:
    def test_healthy_current_ratio(self):
        """Current Ratio = Current Assets / Current Liabilities"""
        bs = _make_bs([
            ("Current Assets", "Cash", "150000", "2024-12"),
            ("Current Liabilities", "AP", "50000", "2024-12"),
        ])
        result = calculate_ratios(RatioInput(statements=[bs]))
        assert result.current_ratio == Decimal("3")

    def test_zero_liabilities(self):
        """Zero current liabilities → current ratio is None."""
        bs = _make_bs([
            ("Current Assets", "Cash", "100000", "2024-12"),
            ("Current Liabilities", "AP", "0", "2024-12"),
        ])
        result = calculate_ratios(RatioInput(statements=[bs]))
        assert result.current_ratio is None


class TestMoMRevenueGrowth:
    def test_positive_mom_growth(self):
        """MoM growth = (this month - last month) / last month"""
        pl = _make_pl([
            ("Revenue", "Sales", "100000", "2024-11"),
            ("Revenue", "Sales", "120000", "2024-12"),
        ])
        result = calculate_ratios(RatioInput(statements=[pl]))
        assert result.mom_revenue_growth == Decimal("0.20")

    def test_negative_mom_growth(self):
        """Revenue declined MoM → negative growth."""
        pl = _make_pl([
            ("Revenue", "Sales", "100000", "2024-11"),
            ("Revenue", "Sales", "80000", "2024-12"),
        ])
        result = calculate_ratios(RatioInput(statements=[pl]))
        assert result.mom_revenue_growth == Decimal("-0.20")

    def test_single_period_no_growth(self):
        """Only one period → cannot compute MoM growth → None."""
        pl = _make_pl([
            ("Revenue", "Sales", "100000", "2024-12"),
        ])
        result = calculate_ratios(RatioInput(statements=[pl]))
        assert result.mom_revenue_growth is None


class TestRevenuePerEmployee:
    def test_revenue_per_employee(self):
        """Revenue per employee = Revenue / headcount."""
        pl = _make_pl([
            ("Revenue", "Sales", "1200000", "2024-12"),
        ])
        result = calculate_ratios(RatioInput(statements=[pl], headcount=10))
        assert result.revenue_per_employee == Decimal("120000")

    def test_no_headcount(self):
        """No headcount provided → revenue_per_employee is None."""
        pl = _make_pl([("Revenue", "Sales", "100000", "2024-12")])
        result = calculate_ratios(RatioInput(statements=[pl]))
        assert result.revenue_per_employee is None


class TestPeriodLabel:
    def test_period_from_pl(self):
        """Period label comes from the latest statement period_end."""
        pl = _make_pl([("Revenue", "Sales", "100000", "2024-06")])
        result = calculate_ratios(RatioInput(statements=[pl]))
        assert result.period == "2024-12"  # period_end of the statement
