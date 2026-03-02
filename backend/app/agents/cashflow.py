"""
agents/cashflow.py — DSPy module for cash flow analysis and forecast narratives.
Uses Claude Sonnet for structured forecast narratives.
Uses Claude Haiku for quick runway Q&A in Slack.
"""
import json
import dspy


class CashflowAnalyzer(dspy.Module):
    """
    Generates a cash flow forecast narrative from runway/burn tool outputs.
    Model: Claude Sonnet — forecast narratives, structured summaries.
    """

    def __init__(self) -> None:
        super().__init__()
        self.analyze = dspy.ChainOfThought(
            "tool_results: str, months: int -> narrative: str"
        )

    def forward(self, tool_results: dict, months: int = 6) -> dspy.Prediction:
        """
        Generate cash flow forecast narrative.

        Args:
            tool_results: Runway and ratio outputs from deterministic tools.
            months: Forecast horizon in months (3 or 6).

        Returns:
            dspy.Prediction with .narrative (str).
        """
        return self.analyze(
            tool_results=json.dumps(tool_results, default=str),
            months=months,
        )
