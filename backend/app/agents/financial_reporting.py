"""
agents/financial_reporting.py — DSPy module for financial report generation.
Uses Claude Sonnet (primary workhorse for document generation).
LangGraph calls this module as a node inside the orchestrator graph.
"""
import json
import dspy


class FinancialReportGenerator(dspy.Module):
    """
    Generates a structured monthly financial report from tool outputs.
    Model: Claude Sonnet — report generation, structured financial summaries.
    """

    def __init__(self) -> None:
        super().__init__()
        self.generate = dspy.ChainOfThought(
            "tool_results: str, financial_data: str -> report: str"
        )

    def forward(self, tool_results: dict, financial_data: dict) -> dspy.Prediction:
        """
        Generate a financial report narrative.

        Args:
            tool_results: Computed ratios, runway, budget, anomalies from tools.
            financial_data: Raw financial statement data (context only).

        Returns:
            dspy.Prediction with .report (str) containing the formatted report.
        """
        return self.generate(
            tool_results=json.dumps(tool_results, default=str),
            financial_data=json.dumps(financial_data, default=str),
        )
