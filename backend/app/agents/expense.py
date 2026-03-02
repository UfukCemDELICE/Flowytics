"""
agents/expense.py — DSPy modules for expense analysis.

ExpenseSummarizer: Claude Sonnet — expense analysis summaries, budget reports.
StrategicAnalyzer: Claude Opus — strategic recommendations, multi-signal analysis.
"""
import json
import dspy


class ExpenseSummarizer(dspy.Module):
    """
    Summarizes budget variance and anomaly data into a concise narrative.
    Model: Claude Sonnet — structured expense summaries.
    """

    def __init__(self) -> None:
        super().__init__()
        self.summarize = dspy.ChainOfThought(
            "tool_results: str -> summary: str"
        )

    def forward(self, tool_results: dict) -> dspy.Prediction:
        """
        Generate an expense summary.

        Args:
            tool_results: Budget and anomaly outputs from deterministic tools.

        Returns:
            dspy.Prediction with .summary (str).
        """
        return self.summarize(
            tool_results=json.dumps(tool_results, default=str),
        )


class StrategicAnalyzer(dspy.Module):
    """
    Performs deep multi-signal strategic analysis.
    Model: Claude Opus — complex financial reasoning, strategic recommendations.
    Use sparingly — expensive.
    """

    def __init__(self) -> None:
        super().__init__()
        self.analyze = dspy.ChainOfThought(
            "tool_results: str, financial_data: str, user_question: str"
            " -> analysis: str, recommendations: str, risks: str"
        )

    def forward(
        self,
        tool_results: dict,
        financial_data: dict,
        user_question: str,
    ) -> dspy.Prediction:
        """
        Generate a strategic analysis with recommendations and risk factors.

        Args:
            tool_results: All tool outputs (ratios, runway, budget, anomalies).
            financial_data: Raw financial statement context.
            user_question: The strategic question from the user.

        Returns:
            dspy.Prediction with .analysis, .recommendations, .risks (all str).
        """
        return self.analyze(
            tool_results=json.dumps(tool_results, default=str),
            financial_data=json.dumps(financial_data, default=str),
            user_question=user_question,
        )
