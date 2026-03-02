"""
Tests for tools/runway.py — burn rate and runway calculations.
Uses known cash flow data with expected outputs verified by hand.
"""
from datetime import date
from decimal import Decimal

import pytest

from backend.app.models.schemas import FinancialRow, FinancialStatement, RunwayInput
from backend.app.tools.runway import calculate_runway


def _make_cf(rows: list[tuple[str, str, str, str]]) -> FinancialStatement:
    return FinancialStatement(
        statement_type="cash_flow",
        company_name="TestCo",
        currency="USD",
        period_start=date(2024, 1, 1),
        period_end=date(2024, 12, 31),
        rows=[
            FinancialRow(category=r[0], subcategory=r[1], amount=Decimal(r[2]), period=r[3])
            for r in rows
        ],
    )


class TestBurnRate:
    def test_simple_burn_rate(self):
        """Burn rate = average of last 3 months net cash outflow."""
        cf = _make_cf([
            ("Net Cash", "Operating", "-50000", "2024-10"),
            ("Net Cash", "Operating", "-60000", "2024-11"),
            ("Net Cash", "Operating", "-40000", "2024-12"),
        ])
        result = calculate_runway(RunwayInput(cash_flow_statement=cf, current_cash=Decimal("500000")))
        # Outflows: 50000, 60000, 40000 → average = 50000
        assert result.monthly_burn_rate == Decimal("50000")

    def test_cash_flow_positive_no_burn(self):
        """Cash flow positive company → runway is None, alert is OK."""
        cf = _make_cf([
            ("Net Cash", "Operating", "10000", "2024-10"),
            ("Net Cash", "Operating", "20000", "2024-11"),
            ("Net Cash", "Operating", "15000", "2024-12"),
        ])
        result = calculate_runway(RunwayInput(cash_flow_statement=cf, current_cash=Decimal("500000")))
        assert result.monthly_burn_rate <= Decimal("0")
        assert result.runway_months is None
        assert result.alert.level == "OK"

    def test_fewer_than_3_months(self):
        """Uses available months when fewer than 3."""
        cf = _make_cf([
            ("Net Cash", "Operating", "-80000", "2024-11"),
            ("Net Cash", "Operating", "-100000", "2024-12"),
        ])
        result = calculate_runway(RunwayInput(cash_flow_statement=cf, current_cash=Decimal("300000")))
        assert result.monthly_burn_rate == Decimal("90000")


class TestRunwayMonths:
    def test_runway_calculation(self):
        """Runway = Current Cash / Monthly Burn Rate"""
        cf = _make_cf([
            ("Net Cash", "Operating", "-100000", "2024-10"),
            ("Net Cash", "Operating", "-100000", "2024-11"),
            ("Net Cash", "Operating", "-100000", "2024-12"),
        ])
        result = calculate_runway(RunwayInput(cash_flow_statement=cf, current_cash=Decimal("600000")))
        assert result.runway_months == Decimal("6")

    def test_critical_runway(self):
        """Less than 3 months → CRITICAL alert."""
        cf = _make_cf([
            ("Net Cash", "Operating", "-200000", "2024-10"),
            ("Net Cash", "Operating", "-200000", "2024-11"),
            ("Net Cash", "Operating", "-200000", "2024-12"),
        ])
        result = calculate_runway(RunwayInput(cash_flow_statement=cf, current_cash=Decimal("400000")))
        assert result.runway_months == Decimal("2")
        assert result.alert.level == "CRITICAL"

    def test_warning_runway(self):
        """3-6 months runway → WARNING alert."""
        cf = _make_cf([
            ("Net Cash", "Operating", "-100000", "2024-10"),
            ("Net Cash", "Operating", "-100000", "2024-11"),
            ("Net Cash", "Operating", "-100000", "2024-12"),
        ])
        result = calculate_runway(RunwayInput(cash_flow_statement=cf, current_cash=Decimal("400000")))
        assert result.runway_months == Decimal("4")
        assert result.alert.level == "WARNING"

    def test_ok_runway(self):
        """12+ months runway → OK alert."""
        cf = _make_cf([
            ("Net Cash", "Operating", "-50000", "2024-10"),
            ("Net Cash", "Operating", "-50000", "2024-11"),
            ("Net Cash", "Operating", "-50000", "2024-12"),
        ])
        result = calculate_runway(RunwayInput(cash_flow_statement=cf, current_cash=Decimal("1200000")))
        assert result.runway_months == Decimal("24")
        assert result.alert.level == "OK"


class TestBurnTrend:
    def test_increasing_burn(self):
        """Burn rate consistently growing → trend is 'increasing'."""
        cf = _make_cf([
            ("Net Cash", "Operating", "-50000", "2024-09"),
            ("Net Cash", "Operating", "-60000", "2024-10"),
            ("Net Cash", "Operating", "-80000", "2024-11"),
            ("Net Cash", "Operating", "-110000", "2024-12"),
        ])
        result = calculate_runway(RunwayInput(cash_flow_statement=cf, current_cash=Decimal("1000000")))
        assert result.burn_trend == "increasing"

    def test_stable_burn(self):
        """Burn rate constant → trend is 'stable'."""
        cf = _make_cf([
            ("Net Cash", "Operating", "-100000", "2024-09"),
            ("Net Cash", "Operating", "-100000", "2024-10"),
            ("Net Cash", "Operating", "-100000", "2024-11"),
            ("Net Cash", "Operating", "-100000", "2024-12"),
        ])
        result = calculate_runway(RunwayInput(cash_flow_statement=cf, current_cash=Decimal("1000000")))
        assert result.burn_trend == "stable"

    def test_no_data(self):
        """No data → returns safe defaults with CRITICAL alert."""
        cf = _make_cf([])
        result = calculate_runway(RunwayInput(cash_flow_statement=cf, current_cash=Decimal("100000")))
        assert result.alert.level == "CRITICAL"
        assert result.runway_months is None
