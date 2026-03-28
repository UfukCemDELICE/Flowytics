"""
Tests for Slack Block Kit formatting quality.

Validates that all message formatters produce valid Block Kit structures,
handle edge cases (empty text, very long text, None metrics), and include
required visual elements (headers, footers, emoji indicators).
"""

from decimal import Decimal
import pytest

from backend.app.integrations.slack import (
    SlackClient,
    _fmt_currency,
    _fmt_pct,
    _split_into_sections,
    _BRAND_FOOTER,
)


# ── Utility function tests ─────────────────────────────────────

class TestCurrencyFormatter:
    def test_positive(self):
        assert _fmt_currency(50000) == "$50,000"

    def test_negative(self):
        assert _fmt_currency(-8000) == "-$8,000"

    def test_zero(self):
        assert _fmt_currency(0) == "$0"

    def test_decimal(self):
        assert _fmt_currency(Decimal("123456.78")) == "$123,457"

    def test_none(self):
        assert _fmt_currency(None) == "N/A"

    def test_none_custom_fallback(self):
        assert _fmt_currency(None, "—") == "—"


class TestPercentFormatter:
    def test_positive(self):
        assert _fmt_pct(15.5) == "15.5%"

    def test_negative(self):
        assert _fmt_pct(Decimal("-8.3")) == "-8.3%"

    def test_zero(self):
        assert _fmt_pct(0) == "0.0%"

    def test_none(self):
        assert _fmt_pct(None) == "N/A"


class TestSectionSplitter:
    def test_short_text(self):
        result = _split_into_sections("Hello world")
        assert result == ["Hello world"]

    def test_long_text_splits_on_paragraphs(self):
        # Create text with multiple paragraphs that exceed limit
        para = "A" * 1500
        text = f"{para}\n\n{para}\n\n{para}"
        result = _split_into_sections(text)
        assert len(result) >= 2
        for chunk in result:
            assert len(chunk) <= 2900

    def test_single_huge_paragraph(self):
        text = "B" * 6000
        result = _split_into_sections(text)
        assert len(result) >= 3
        for chunk in result:
            assert len(chunk) <= 2900

    def test_empty_text(self):
        result = _split_into_sections("")
        assert result == [""]


# ── Block Kit structure tests ───────────────────────────────────

class TestCFOResponseBlock:
    def setup_method(self):
        self.client = SlackClient()

    def test_basic_structure(self):
        blocks = self.client.format_cfo_response_block("Your burn rate is $10K/mo.")
        # Must have: header, section(s), divider, context
        types = [b["type"] for b in blocks]
        assert types[0] == "header"
        assert "section" in types
        assert "divider" in types
        assert types[-1] == "context"

    def test_header_text(self):
        blocks = self.client.format_cfo_response_block("Test")
        header = blocks[0]
        assert "AI CFO" in header["text"]["text"]

    def test_footer_has_brand_and_timestamp(self):
        blocks = self.client.format_cfo_response_block("Test")
        footer = blocks[-1]
        footer_texts = [e["text"] for e in footer["elements"]]
        assert any("Flowytics" in t for t in footer_texts)
        assert any("UTC" in t for t in footer_texts)

    def test_long_text_splits_into_multiple_sections(self):
        long_text = ("Paragraph one. " * 200) + "\n\n" + ("Paragraph two. " * 200)
        blocks = self.client.format_cfo_response_block(long_text)
        section_blocks = [b for b in blocks if b["type"] == "section"]
        assert len(section_blocks) >= 2

    def test_empty_text(self):
        blocks = self.client.format_cfo_response_block("")
        assert len(blocks) >= 3  # header + section + divider + context


class TestProactiveAlertBlock:
    def setup_method(self):
        self.client = SlackClient()

    def test_warning_severity(self):
        blocks = self.client.format_proactive_alert_block("Low runway", severity="warning")
        header = blocks[0]["text"]["text"]
        assert "WARNING" in header
        assert "⚠️" in header

    def test_critical_severity(self):
        blocks = self.client.format_proactive_alert_block("Runway critical", severity="critical")
        header = blocks[0]["text"]["text"]
        assert "CRITICAL" in header
        assert "🚨" in header

    def test_has_cta_section(self):
        blocks = self.client.format_proactive_alert_block("Alert text")
        all_text = " ".join(str(b) for b in blocks)
        assert "What to do next" in all_text
        assert "Dashboard" in all_text

    def test_has_footer(self):
        blocks = self.client.format_proactive_alert_block("Test")
        assert blocks[-1]["type"] == "context"


class TestMonthlyReportBlock:
    def setup_method(self):
        self.client = SlackClient()

    def test_full_metrics(self):
        metrics = {
            "mrr": Decimal("25000"),
            "mrr_growth": Decimal("15.5"),
            "net_burn": Decimal("8000"),
            "runway_months": Decimal("12.5"),
            "cash_balance": Decimal("100000"),
        }
        blocks = self.client.format_monthly_cfo_report_block(
            metrics=metrics,
            executive_summary="Strong growth month.",
            key_consideration="Monitor cloud costs.",
            tenant_name="Acme Inc",
        )
        all_text = " ".join(str(b) for b in blocks)

        # Check KPI formatting
        assert "$25,000" in all_text
        assert "$8,000" in all_text
        assert "$100,000" in all_text
        assert "15.5%" in all_text
        assert "Acme Inc" in all_text

    def test_runway_status_badges(self):
        # Critical runway (<3 months)
        metrics = {"mrr": 0, "mrr_growth": 0, "net_burn": 10000, "runway_months": 2, "cash_balance": 20000}
        blocks = self.client.format_monthly_cfo_report_block(metrics=metrics, executive_summary="", key_consideration="")
        all_text = " ".join(str(b) for b in blocks)
        assert "🔴" in all_text

        # Healthy runway (>12 months)
        metrics["runway_months"] = 18
        blocks = self.client.format_monthly_cfo_report_block(metrics=metrics, executive_summary="", key_consideration="")
        all_text = " ".join(str(b) for b in blocks)
        assert "🟢" in all_text

    def test_growth_indicators(self):
        # Positive growth
        metrics = {"mrr": 5000, "mrr_growth": Decimal("20"), "net_burn": 0, "runway_months": 99, "cash_balance": 0}
        blocks = self.client.format_monthly_cfo_report_block(metrics=metrics, executive_summary="", key_consideration="")
        all_text = " ".join(str(b) for b in blocks)
        assert "📈" in all_text

        # Negative growth
        metrics["mrr_growth"] = Decimal("-5")
        blocks = self.client.format_monthly_cfo_report_block(metrics=metrics, executive_summary="", key_consideration="")
        all_text = " ".join(str(b) for b in blocks)
        assert "📉" in all_text

    def test_none_metrics_handled(self):
        """None values should produce 'N/A' fallbacks, not crash."""
        metrics = {"mrr": None, "mrr_growth": None, "net_burn": None, "runway_months": None, "cash_balance": None}
        blocks = self.client.format_monthly_cfo_report_block(metrics=metrics, executive_summary="Test", key_consideration="Test")
        all_text = " ".join(str(b) for b in blocks)
        assert "N/A" in all_text

    def test_has_quick_actions(self):
        metrics = {"mrr": 0, "mrr_growth": 0, "net_burn": 0, "runway_months": 12, "cash_balance": 50000}
        blocks = self.client.format_monthly_cfo_report_block(metrics=metrics, executive_summary="", key_consideration="")
        all_text = " ".join(str(b) for b in blocks)
        assert "Dive deeper" in all_text


class TestErrorBlock:
    def setup_method(self):
        self.client = SlackClient()

    def test_basic_error(self):
        blocks = self.client.format_error_block("Connection Failed", "Something went wrong.")
        assert blocks[0]["type"] == "header"
        assert "Connection Failed" in blocks[0]["text"]["text"]
        assert "❌" in blocks[0]["text"]["text"]

    def test_with_cta(self):
        blocks = self.client.format_error_block("Error", "Details", cta="Reconnect now")
        all_text = " ".join(str(b) for b in blocks)
        assert "Reconnect now" in all_text
        assert "Action required" in all_text

    def test_without_cta(self):
        blocks = self.client.format_error_block("Error", "No action needed.")
        # Should not have an action section
        section_texts = [b.get("text", {}).get("text", "") for b in blocks if b["type"] == "section"]
        assert not any("Action required" in t for t in section_texts)


class TestStaleDataWarningBlock:
    def setup_method(self):
        self.client = SlackClient()

    def test_structure(self):
        blocks = self.client.format_stale_data_warning_block("Data is 3 days old.")
        assert len(blocks) == 2  # warning section + divider
        assert blocks[0]["type"] == "section"
        assert blocks[1]["type"] == "divider"

    def test_has_sync_button(self):
        blocks = self.client.format_stale_data_warning_block("Stale data")
        accessory = blocks[0].get("accessory", {})
        assert accessory["type"] == "button"
        assert "Sync" in accessory["text"]["text"]

    def test_warning_label(self):
        blocks = self.client.format_stale_data_warning_block("Old data")
        text = blocks[0]["text"]["text"]
        assert "Data Freshness Warning" in text
