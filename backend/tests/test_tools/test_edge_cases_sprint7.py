"""
Sprint 7 Edge Cases: Empty QBO, zero revenue, negative cash, single transaction, malformed data.

Tests all financial tools and services against degenerate inputs that a real startup
might produce — pre-revenue companies, brand new QBO accounts with no history, companies
that have already exhausted their cash, and corrupted data from QBO API quirks.
"""

from datetime import date
from decimal import Decimal

import pytest

from backend.app.tools.burn_rate import calculate_burn_rate
from backend.app.tools.runway import calculate_runway
from backend.app.tools.cash_forecast import calculate_cash_forecast
from backend.app.tools.anomaly import calculate_anomalies
from backend.app.tools.fundraising import calculate_fundraising_readiness
from backend.app.tools.scenario import calculate_scenario_impact
from backend.app.tools.financial_summary import parse_qbo_to_financial_summary
from backend.app.tools.schemas import (
    FinancialSummary, MonthlyFinancial, BurnRateResult, ScenarioChange,
)


# ── Helper factories ────────────────────────────────────────────

def _empty_summary(cash: str = "0") -> FinancialSummary:
    return FinancialSummary(current_cash_balance=Decimal(cash), monthly_financials=[])


def _zero_revenue_summary(months: int = 6, cash: str = "50000") -> FinancialSummary:
    """Pre-revenue startup: expenses only, zero income across all months."""
    return FinancialSummary(
        current_cash_balance=Decimal(cash),
        monthly_financials=[
            MonthlyFinancial(
                month_start=date(2025, i + 1, 1),
                total_revenue=Decimal("0"),
                total_expenses=Decimal("8000"),
                net_income=Decimal("-8000"),
            )
            for i in range(months)
        ],
    )


def _negative_cash_summary() -> FinancialSummary:
    """Company that has overdrawn its account (negative cash balance)."""
    return FinancialSummary(
        current_cash_balance=Decimal("-5000"),
        monthly_financials=[
            MonthlyFinancial(
                month_start=date(2025, i + 1, 1),
                total_revenue=Decimal("2000"),
                total_expenses=Decimal("10000"),
                net_income=Decimal("-8000"),
            )
            for i in range(3)
        ],
    )


def _single_transaction_summary() -> FinancialSummary:
    """Brand new QBO account with only 1 month of data."""
    return FinancialSummary(
        current_cash_balance=Decimal("100000"),
        monthly_financials=[
            MonthlyFinancial(
                month_start=date(2025, 1, 1),
                total_revenue=Decimal("5000"),
                total_expenses=Decimal("3000"),
                net_income=Decimal("2000"),
            ),
        ],
    )


def _all_zeros_summary() -> FinancialSummary:
    """QBO account connected but all values are zero (no real activity)."""
    return FinancialSummary(
        current_cash_balance=Decimal("0"),
        monthly_financials=[
            MonthlyFinancial(
                month_start=date(2025, i + 1, 1),
                total_revenue=Decimal("0"),
                total_expenses=Decimal("0"),
                net_income=Decimal("0"),
            )
            for i in range(3)
        ],
    )


# ════════════════════════════════════════════════════════════════
#  1. EMPTY QBO (no monthly data at all)
# ════════════════════════════════════════════════════════════════

class TestEmptyQBO:
    def test_burn_rate_empty(self):
        result = calculate_burn_rate.invoke({"summary": _empty_summary()})
        assert result.net_burn_monthly == Decimal("0")
        assert result.gross_burn_monthly == Decimal("0")
        assert result.trend == "stable"
        assert result.period_months == 0

    def test_runway_empty(self):
        summary = _empty_summary(cash="50000")
        burn = BurnRateResult(
            net_burn_monthly=Decimal("0"),
            gross_burn_monthly=Decimal("0"),
            burn_multiple=None, trend="stable", trend_slope=Decimal("0"), period_months=0
        )
        result = calculate_runway.invoke({"summary": summary, "burn_rate": burn})
        assert result.runway_months == Decimal("9999")
        assert result.runway_status == "healthy"

    def test_cash_forecast_empty(self):
        result = calculate_cash_forecast.invoke({"summary": _empty_summary()})
        assert len(result.weeks) == 0
        assert result.zero_cash_week is None

    def test_anomalies_empty(self):
        result = calculate_anomalies.invoke({"summary": _empty_summary()})
        assert len(result.anomalies) == 0
        assert result.scan_period_months == 0

    def test_fundraising_empty(self):
        result = calculate_fundraising_readiness.invoke({"summary": _empty_summary()})
        assert result.readiness_score == 0
        assert "No financial history" in result.gaps[0]

    def test_scenario_empty(self):
        changes = [ScenarioChange(type="hire", description="New engineer", monthly_impact=Decimal("10000"))]
        result = calculate_scenario_impact.invoke({"summary": _empty_summary(cash="100000"), "changes": changes})
        assert result.current_burn == Decimal("0")
        assert result.new_burn == Decimal("10000")
        assert result.delta_burn == Decimal("10000")
        # New runway = 100000/10000 = 10.00 months
        assert result.new_runway == Decimal("10.00")


# ════════════════════════════════════════════════════════════════
#  2. ZERO REVENUE (pre-revenue startup)
# ════════════════════════════════════════════════════════════════

class TestZeroRevenue:
    def test_burn_rate_zero_revenue(self):
        summary = _zero_revenue_summary()
        result = calculate_burn_rate.invoke({"summary": summary})
        # All months have net_income = -8000, so net burn = 8000
        assert result.net_burn_monthly == Decimal("8000")
        assert result.gross_burn_monthly == Decimal("8000")
        assert result.period_months == 6

    def test_runway_zero_revenue(self):
        summary = _zero_revenue_summary()
        burn = calculate_burn_rate.invoke({"summary": summary})
        result = calculate_runway.invoke({"summary": summary, "burn_rate": burn})
        # 50000 / 8000 = 6.25 months
        assert result.runway_months == Decimal("6.25")
        assert result.runway_status == "monitor"

    def test_cash_forecast_zero_revenue(self):
        summary = _zero_revenue_summary()
        result = calculate_cash_forecast.invoke({"summary": summary})
        assert len(result.weeks) == 13
        # Zero inflow, ~$1847/week outflow → balance drops every week
        assert all(w.projected_inflow == Decimal("0.00") for w in result.weeks)
        # Balance is strictly declining
        assert result.weeks[-1].projected_balance < result.weeks[0].projected_balance
        # With $50k and ~$1848/week, 13 weeks isn't enough to deplete (needs ~27 weeks)
        # So zero_cash_week should be None within a 13-week forecast
        assert result.zero_cash_week is None

    def test_fundraising_zero_revenue(self):
        summary = _zero_revenue_summary()
        result = calculate_fundraising_readiness.invoke({"summary": summary})
        # Pre-revenue should still produce a valid result
        assert result.readiness_score >= 0
        assert any("Pre-revenue" in g or "revenue" in g.lower() for g in result.gaps)
        assert result.metrics.mrr == Decimal("0")
        assert result.metrics.arr == Decimal("0")

    def test_anomalies_zero_revenue(self):
        summary = _zero_revenue_summary()
        result = calculate_anomalies.invoke({"summary": summary})
        # Flat expenses across all months = no anomalies
        assert len(result.anomalies) == 0

    def test_scenario_zero_revenue_hire(self):
        summary = _zero_revenue_summary()
        changes = [ScenarioChange(type="hire", description="CTO hire", monthly_impact=Decimal("15000"))]
        result = calculate_scenario_impact.invoke({"summary": summary, "changes": changes})
        # Current burn is $8000, new burn should be $23000
        assert result.new_burn == result.current_burn + Decimal("15000")
        # Runway should drop significantly
        assert result.new_runway < result.current_runway


# ════════════════════════════════════════════════════════════════
#  3. NEGATIVE CASH (overdrawn company)
# ════════════════════════════════════════════════════════════════

class TestNegativeCash:
    def test_runway_negative_cash(self):
        summary = _negative_cash_summary()
        burn = calculate_burn_rate.invoke({"summary": summary})
        result = calculate_runway.invoke({"summary": summary, "burn_rate": burn})
        # Negative cash with positive burn = 0 months, critical
        assert result.runway_months == Decimal("0")
        assert result.runway_status == "critical"
        assert result.cash_zero_date == date.today()

    def test_cash_forecast_negative_starting_balance(self):
        summary = _negative_cash_summary()
        result = calculate_cash_forecast.invoke({"summary": summary})
        assert len(result.weeks) == 13
        # Starting from negative, first week is already below zero
        assert result.zero_cash_week == 1
        assert result.weeks[0].projected_balance < Decimal("0")

    def test_fundraising_negative_cash(self):
        summary = _negative_cash_summary()
        result = calculate_fundraising_readiness.invoke({"summary": summary})
        # Low runway gap should be flagged
        assert any("runway" in g.lower() or "critically" in g.lower() for g in result.gaps)

    def test_scenario_negative_cash_cut_expense(self):
        summary = _negative_cash_summary()
        changes = [ScenarioChange(type="cut_expense", description="Reduce cloud costs", monthly_impact=Decimal("-5000"))]
        result = calculate_scenario_impact.invoke({"summary": summary, "changes": changes})
        # Cutting $5000 from burn should still result in new_burn > 0
        assert result.new_burn < result.current_burn


# ════════════════════════════════════════════════════════════════
#  4. SINGLE TRANSACTION / ONE MONTH
# ════════════════════════════════════════════════════════════════

class TestSingleTransaction:
    def test_burn_rate_one_month(self):
        summary = _single_transaction_summary()
        result = calculate_burn_rate.invoke({"summary": summary})
        # net_income = +2000, so net burn = -2000 (profitable)
        assert result.net_burn_monthly == Decimal("-2000")
        assert result.trend_slope == Decimal("0")  # Cannot compute slope from 1 point
        assert result.period_months == 1

    def test_runway_one_month_profitable(self):
        summary = _single_transaction_summary()
        burn = calculate_burn_rate.invoke({"summary": summary})
        result = calculate_runway.invoke({"summary": summary, "burn_rate": burn})
        # Profitable company = infinite runway
        assert result.runway_months == Decimal("9999")
        assert result.runway_status == "healthy"

    def test_cash_forecast_one_month(self):
        summary = _single_transaction_summary()
        result = calculate_cash_forecast.invoke({"summary": summary})
        # Should still produce 13 weeks from just 1 month of data
        assert len(result.weeks) == 13

    def test_anomalies_one_month(self):
        summary = _single_transaction_summary()
        result = calculate_anomalies.invoke({"summary": summary})
        # Fewer than 3 months = cannot compute z-scores
        assert len(result.anomalies) == 0
        assert result.scan_period_months == 1

    def test_fundraising_one_month(self):
        summary = _single_transaction_summary()
        result = calculate_fundraising_readiness.invoke({"summary": summary})
        # Has revenue but only 1 month of data → no growth rate
        assert result.metrics.mrr == Decimal("5000")
        assert result.metrics.mrr_growth_rate is None  # Can't compute with 1 month


# ════════════════════════════════════════════════════════════════
#  5. ALL ZEROS (connected but no real activity)
# ════════════════════════════════════════════════════════════════

class TestAllZeros:
    def test_burn_rate_all_zeros(self):
        summary = _all_zeros_summary()
        result = calculate_burn_rate.invoke({"summary": summary})
        assert result.net_burn_monthly == Decimal("0")
        assert result.gross_burn_monthly == Decimal("0")
        assert result.trend == "stable"

    def test_runway_all_zeros(self):
        summary = _all_zeros_summary()
        burn = calculate_burn_rate.invoke({"summary": summary})
        result = calculate_runway.invoke({"summary": summary, "burn_rate": burn})
        # Zero burn = infinite runway even with zero cash
        assert result.runway_months == Decimal("9999")
        assert result.runway_status == "healthy"

    def test_cash_forecast_all_zeros(self):
        summary = _all_zeros_summary()
        result = calculate_cash_forecast.invoke({"summary": summary})
        # 13 weeks of flat zero
        assert len(result.weeks) == 13
        assert all(w.projected_balance == Decimal("0.00") for w in result.weeks)
        assert result.zero_cash_week is None  # Zero is at zero but not below

    def test_fundraising_all_zeros(self):
        summary = _all_zeros_summary()
        result = calculate_fundraising_readiness.invoke({"summary": summary})
        assert result.readiness_score < 50  # Should be penalized heavily
        assert result.metrics.mrr == Decimal("0")


# ════════════════════════════════════════════════════════════════
#  6. MALFORMED QBO DATA (parser hardening)
# ════════════════════════════════════════════════════════════════

class TestMalformedData:
    def test_empty_monthly_data_array(self):
        """monthly_data key exists but is an empty list."""
        pl_data = {"monthly_data": []}
        bs_data = {"current_cash_balance": "1000"}
        result = parse_qbo_to_financial_summary.invoke({"pl_data": pl_data, "bs_data": bs_data})
        assert result.current_cash_balance == Decimal("0")
        assert len(result.monthly_financials) == 0

    def test_missing_month_field(self):
        """Row without a month field should be skipped."""
        pl_data = {"monthly_data": [
            {"revenue": "1000", "expenses": "500", "net_income": "500"},  # missing month
            {"month": "2025-02", "revenue": "2000", "expenses": "800", "net_income": "1200"},
        ]}
        bs_data = {"current_cash_balance": "5000"}
        result = parse_qbo_to_financial_summary.invoke({"pl_data": pl_data, "bs_data": bs_data})
        # First row skipped, second parsed
        assert len(result.monthly_financials) == 1
        assert result.monthly_financials[0].total_revenue == Decimal("2000")

    def test_null_revenue_treated_as_zero(self):
        """Revenue field is None → should be treated as 0."""
        pl_data = {"monthly_data": [
            {"month": "2025-01", "revenue": None, "expenses": "500", "net_income": "-500"},
        ]}
        bs_data = {"current_cash_balance": "0"}
        result = parse_qbo_to_financial_summary.invoke({"pl_data": pl_data, "bs_data": bs_data})
        assert len(result.monthly_financials) == 1
        assert result.monthly_financials[0].total_revenue == Decimal("0")

    def test_no_monthly_data_key(self):
        """QBO response with no monthly_data key at all."""
        pl_data = {"Header": {"ReportName": "ProfitAndLoss"}, "Rows": {}}
        bs_data = {}
        result = parse_qbo_to_financial_summary.invoke({"pl_data": pl_data, "bs_data": bs_data})
        assert result.current_cash_balance == Decimal("0")
        assert len(result.monthly_financials) == 0

    def test_null_cash_balance(self):
        """Balance sheet with null cash balance."""
        pl_data = {"monthly_data": [
            {"month": "2025-01", "revenue": "1000", "expenses": "500", "net_income": "500"},
        ]}
        bs_data = {"current_cash_balance": None}
        result = parse_qbo_to_financial_summary.invoke({"pl_data": pl_data, "bs_data": bs_data})
        assert result.current_cash_balance == Decimal("0")

    def test_completely_empty_dicts(self):
        """Both pl_data and bs_data are empty dicts."""
        result = parse_qbo_to_financial_summary.invoke({"pl_data": {}, "bs_data": {}})
        assert result.current_cash_balance == Decimal("0")
        assert len(result.monthly_financials) == 0
