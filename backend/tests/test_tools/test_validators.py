"""
Tests for tools/validators.py — cross-validation of LLM vs tool outputs.
Ensures discrepancies are detected and severity is correctly assigned.
"""
from decimal import Decimal

import pytest

from backend.app.tools.validators import cross_validate


class TestCleanValidation:
    def test_no_numbers_in_llm_text(self):
        """LLM text with no extractable numbers → clean, no discrepancies."""
        tool_numbers = {"burn_rate": Decimal("50000"), "runway_months": Decimal("12")}
        llm_text = "Your runway is healthy. Consider optimizing your marketing spend."
        result = cross_validate(tool_numbers, llm_text)
        assert result.is_clean
        assert len(result.discrepancies) == 0

    def test_matching_numbers(self):
        """LLM repeats tool numbers exactly → clean."""
        tool_numbers = {"runway_months": Decimal("6")}
        llm_text = "runway_months: 6"
        result = cross_validate(tool_numbers, llm_text)
        assert result.is_clean


class TestWarningDiscrepancy:
    def test_small_discrepancy_is_warning(self):
        """5% discrepancy → WARNING (between 1% and 10%)."""
        tool_numbers = {"burn_rate": Decimal("100000")}
        llm_text = "burn_rate: 105000"
        result = cross_validate(tool_numbers, llm_text)
        assert not result.is_clean
        assert len(result.discrepancies) == 1
        assert result.discrepancies[0].severity == "WARNING"


class TestErrorDiscrepancy:
    def test_large_discrepancy_is_error(self):
        """50% discrepancy → ERROR (> 10%)."""
        tool_numbers = {"runway_months": Decimal("12")}
        llm_text = "runway_months: 18"
        result = cross_validate(tool_numbers, llm_text)
        assert not result.is_clean
        assert any(d.severity == "ERROR" for d in result.discrepancies)

    def test_discrepancy_percentage_is_correct(self):
        """Discrepancy percentage is computed correctly."""
        tool_numbers = {"gross_margin": Decimal("0.60")}
        llm_text = "gross_margin: 0.72"
        result = cross_validate(tool_numbers, llm_text)
        if result.discrepancies:
            disc = result.discrepancies[0]
            # (0.72 - 0.60) / 0.60 * 100 = 20%
            assert abs(disc.discrepancy_pct - Decimal("20")) < Decimal("0.1")


class TestToolValuesPreserved:
    def test_tool_values_are_preserved(self):
        """Tool values in discrepancy record match the input tool values."""
        tool_numbers = {"burn_rate": Decimal("80000")}
        llm_text = "burn_rate: 120000"
        result = cross_validate(tool_numbers, llm_text)
        if result.discrepancies:
            disc = result.discrepancies[0]
            assert disc.tool_value == Decimal("80000")
            assert disc.llm_value == Decimal("120000")
