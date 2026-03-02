"""
Tests for tools/anomaly.py — Z-score anomaly detection.
Uses known datasets where anomalies are predictable.
"""
from datetime import date
from decimal import Decimal

import pytest

from backend.app.models.schemas import AnomalyInput, FinancialRow, FinancialStatement
from backend.app.tools.anomaly import detect_anomalies


def _make_stmt(rows: list[tuple[str, str, str, str]]) -> FinancialStatement:
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


class TestBasicAnomalyDetection:
    def test_spike_detected(self):
        """A 10x spike should be flagged as HIGH anomaly."""
        stmt = _make_stmt([
            ("SaaS Subscriptions", "AWS", "5000", "2024-01"),
            ("SaaS Subscriptions", "AWS", "5200", "2024-02"),
            ("SaaS Subscriptions", "AWS", "4800", "2024-03"),
            ("SaaS Subscriptions", "AWS", "5100", "2024-04"),
            ("SaaS Subscriptions", "AWS", "4900", "2024-05"),
            ("SaaS Subscriptions", "AWS", "50000", "2024-06"),  # spike!
        ])
        result = detect_anomalies(AnomalyInput(statements=[stmt]))
        assert len(result.anomalies) >= 1
        spike = next((a for a in result.anomalies if a.category == "SaaS Subscriptions"), None)
        assert spike is not None
        assert spike.severity in ("HIGH", "MEDIUM")
        assert spike.z_score > Decimal("2")

    def test_no_anomaly_stable_data(self):
        """Stable data with low variance → no anomalies flagged."""
        stmt = _make_stmt([
            ("Rent", "Office", "10000", "2024-01"),
            ("Rent", "Office", "10000", "2024-02"),
            ("Rent", "Office", "10000", "2024-03"),
            ("Rent", "Office", "10000", "2024-04"),
            ("Rent", "Office", "10000", "2024-05"),
            ("Rent", "Office", "10000", "2024-06"),
        ])
        result = detect_anomalies(AnomalyInput(statements=[stmt]))
        rent_anomalies = [a for a in result.anomalies if a.category == "Rent"]
        assert len(rent_anomalies) == 0

    def test_insufficient_data(self):
        """Fewer than 3 months → no anomalies (insufficient data)."""
        stmt = _make_stmt([
            ("Marketing", "Ads", "20000", "2024-11"),
            ("Marketing", "Ads", "25000", "2024-12"),
        ])
        result = detect_anomalies(AnomalyInput(statements=[stmt]))
        assert len(result.anomalies) == 0


class TestNewAndDisappearedCategories:
    def test_new_category_flagged(self):
        """A category that appears for the first time → flagged as new."""
        stmt = _make_stmt([
            ("Payroll", "Engineers", "100000", "2024-01"),
            ("Payroll", "Engineers", "100000", "2024-02"),
            ("Payroll", "Engineers", "100000", "2024-03"),
            ("Payroll", "Engineers", "100000", "2024-04"),
            ("Payroll", "Engineers", "100000", "2024-05"),
            ("Payroll", "Engineers", "100000", "2024-06"),
            # New category in June
            ("Crypto Payment", "BTC", "50000", "2024-06"),
        ])
        result = detect_anomalies(AnomalyInput(statements=[stmt]))
        new_cats = [a for a in result.anomalies if "New category" in a.reason]
        assert len(new_cats) >= 1
        assert any(a.category == "Crypto Payment" for a in new_cats)

    def test_disappeared_category_flagged(self):
        """A category present historically but absent in current period → flagged."""
        stmt = _make_stmt([
            ("Contractor", "Design", "15000", "2024-01"),
            ("Contractor", "Design", "15000", "2024-02"),
            ("Contractor", "Design", "15000", "2024-03"),
            ("Contractor", "Design", "15000", "2024-04"),
            ("Contractor", "Design", "15000", "2024-05"),
            # "Contractor" missing from 2024-06
            ("Payroll", "Engineers", "100000", "2024-06"),
        ])
        result = detect_anomalies(AnomalyInput(statements=[stmt]))
        disappeared = [a for a in result.anomalies if "disappeared" in a.reason.lower()]
        assert len(disappeared) >= 1


class TestSeverityOrdering:
    def test_results_sorted_by_severity(self):
        """HIGH severity anomalies come before LOW severity."""
        stmt = _make_stmt([
            ("Category A", "Sub", "1000", "2024-01"),
            ("Category A", "Sub", "1000", "2024-02"),
            ("Category A", "Sub", "1000", "2024-03"),
            ("Category A", "Sub", "1000", "2024-04"),
            ("Category A", "Sub", "1000", "2024-05"),
            ("Category A", "Sub", "100000", "2024-06"),  # massive spike
        ])
        result = detect_anomalies(AnomalyInput(statements=[stmt]))
        if len(result.anomalies) >= 2:
            severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
            severities = [severity_order[a.severity] for a in result.anomalies]
            assert severities == sorted(severities)
