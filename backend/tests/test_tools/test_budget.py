"""
Tests for tools/budget.py — budget vs actual variance analysis.
Uses known financial data with hand-verified expected outputs.
"""
from datetime import date
from decimal import Decimal

import pytest

from backend.app.models.schemas import BudgetInput, FinancialRow, FinancialStatement
from backend.app.tools.budget import analyze_budget


def _make_pl(rows: list[tuple[str, str, str, str]]) -> FinancialStatement:
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


class TestVarianceCalculation:
    def test_over_budget_warning(self):
        """25% over budget → WARNING alert."""
        pl = _make_pl([
            ("Marketing expense", "Ads", "25000", "2024-11"),
            ("Marketing expense", "Ads", "25000", "2024-12"),
        ])
        budget_targets = {"Marketing expense": Decimal("20000")}
        result = analyze_budget(BudgetInput(statements=[pl], budget_targets=budget_targets))

        marketing = next((c for c in result.categories if c.category == "Marketing expense"), None)
        assert marketing is not None
        assert marketing.alert == "WARNING"
        assert marketing.variance_pct > Decimal("20")

    def test_critical_over_budget(self):
        """60% over budget → CRITICAL alert."""
        pl = _make_pl([
            ("SaaS cost", "Tools", "16000", "2024-11"),
            ("SaaS cost", "Tools", "16000", "2024-12"),
        ])
        budget_targets = {"SaaS cost": Decimal("10000")}
        result = analyze_budget(BudgetInput(statements=[pl], budget_targets=budget_targets))

        saas = next((c for c in result.categories if c.category == "SaaS cost"), None)
        assert saas is not None
        assert saas.alert == "CRITICAL"

    def test_under_budget_ok(self):
        """Under budget → OK alert."""
        pl = _make_pl([
            ("Admin expense", "Office", "8000", "2024-11"),
            ("Admin expense", "Office", "8000", "2024-12"),
        ])
        budget_targets = {"Admin expense": Decimal("10000")}
        result = analyze_budget(BudgetInput(statements=[pl], budget_targets=budget_targets))

        admin = next((c for c in result.categories if c.category == "Admin expense"), None)
        assert admin is not None
        assert admin.alert == "OK"
        assert admin.variance_pct < Decimal("0")


class TestTop5BySpend:
    def test_top5_ordered_by_spend(self):
        """Top 5 categories are sorted by actual spend descending."""
        rows = []
        expenses = [
            ("Payroll expense", "100000"),
            ("Marketing expense", "30000"),
            ("SaaS cost", "15000"),
            ("Rent expense", "12000"),
            ("Travel expense", "5000"),
            ("Admin expense", "2000"),
        ]
        for cat, amount in expenses:
            rows.append((cat, "Sub", amount, "2024-11"))
            rows.append((cat, "Sub", amount, "2024-12"))

        pl = _make_pl(rows)
        result = analyze_budget(BudgetInput(statements=[pl]))

        assert result.top5_by_spend[0] == "Payroll expense"
        assert "Marketing expense" in result.top5_by_spend
        assert len(result.top5_by_spend) <= 5


class TestMoMGrowth:
    def test_mom_growth_calculation(self):
        """MoM growth = (current - prev) / prev."""
        pl = _make_pl([
            ("Marketing expense", "Ads", "10000", "2024-11"),
            ("Marketing expense", "Ads", "12000", "2024-12"),
        ])
        result = analyze_budget(BudgetInput(statements=[pl]))

        marketing = next((c for c in result.categories if c.category == "Marketing expense"), None)
        assert marketing is not None
        assert marketing.mom_growth == Decimal("20")  # 20% growth

    def test_single_period_no_mom(self):
        """Only one period → MoM growth is None."""
        pl = _make_pl([
            ("Marketing expense", "Ads", "10000", "2024-12"),
        ])
        result = analyze_budget(BudgetInput(statements=[pl]))

        marketing = next((c for c in result.categories if c.category == "Marketing expense"), None)
        if marketing:
            assert marketing.mom_growth is None


class TestEmptyStatements:
    def test_no_expense_rows(self):
        """No expense data → empty result, no crash."""
        pl = _make_pl([
            ("Revenue", "Sales", "100000", "2024-12"),
        ])
        result = analyze_budget(BudgetInput(statements=[pl]))
        assert result.categories == []
        assert result.top5_by_spend == []
