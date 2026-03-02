"""
agents/orchestrator.py — LangGraph agent graph for Flowytics.

Graph structure:
  START → fetch_data → run_tools → route_model → [opus|sonnet|haiku] → cross_validate → format_output → END

LangGraph controls FLOW. DSPy modules (called inside nodes) control LLM QUALITY.
"""
from typing import Literal

import dspy
from langgraph.graph import END, START, StateGraph

from backend.app.models.schemas import AgentState, AnomalyInput, BudgetInput, RatioInput, RunwayInput
from backend.app.tools.anomaly import detect_anomalies
from backend.app.tools.budget import analyze_budget
from backend.app.tools.ratios import calculate_ratios
from backend.app.tools.runway import calculate_runway
from backend.app.tools.validators import cross_validate

# ---------------------------------------------------------------------------
# Model selection
# ---------------------------------------------------------------------------

_MODEL_MAP: dict[str, str] = {
    "slack_chat": "claude-haiku-4-5-20250301",
    "slack_deep": "claude-sonnet-4-5-20250514",
    "report_generation": "claude-sonnet-4-5-20250514",
    "forecast_narrative": "claude-sonnet-4-5-20250514",
    "expense_summary": "claude-sonnet-4-5-20250514",
    "cross_statement_analysis": "claude-opus-4-20250514",
    "strategic_recommendation": "claude-opus-4-20250514",
    "multi_signal_analysis": "claude-opus-4-20250514",
}


def select_model(task_type: str) -> str:
    """Route to the appropriate Claude model based on task type."""
    return _MODEL_MAP.get(task_type, "claude-sonnet-4-5-20250514")


def _infer_task_type(state: AgentState) -> str:
    """Infer DSPy task type from AgentState request_type and params."""
    rtype = state["request_type"]
    params = state.get("request_params", {})

    if rtype == "slack":
        question = params.get("question", "").lower()
        upgrade_words = ("analyze", "deep dive", "strategy", "should i", "recommend", "strategic")
        report_words = ("report", "summary", "document", "full")
        if any(w in question for w in upgrade_words):
            return "strategic_recommendation"
        if any(w in question for w in report_words):
            return "report_generation"
        return "slack_chat"

    if rtype == "report":
        return "cross_statement_analysis"
    if rtype == "cashflow":
        return "forecast_narrative"
    if rtype == "expense":
        return "expense_summary"

    return "report_generation"


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------

def fetch_financial_data(state: AgentState) -> AgentState:
    """
    Pull financial data from cache or QuickBooks.
    This node is a pass-through — actual fetching happens in the service layer
    before the graph is invoked. financial_data is pre-populated in state.
    """
    return state


def run_deterministic_tools(state: AgentState) -> AgentState:
    """Run all relevant deterministic tools based on request type."""
    data = state.get("financial_data") or {}
    rtype = state["request_type"]
    results: dict = {}

    # Reconstruct statements from serialized financial_data
    from backend.app.models.schemas import FinancialStatement
    statements = [FinancialStatement(**s) for s in data.get("statements", [])]

    if not statements:
        state["tool_results"] = results
        return state

    if rtype in ("report", "slack"):
        results["ratios"] = calculate_ratios(
            RatioInput(statements=statements)
        ).model_dump(mode="json")

    if rtype in ("cashflow", "report", "slack"):
        from decimal import Decimal
        cf = next((s for s in statements if s.statement_type == "cash_flow"), None)
        if cf:
            current_cash = Decimal(str(data.get("current_cash", "0")))
            results["runway"] = calculate_runway(
                RunwayInput(cash_flow_statement=cf, current_cash=current_cash)
            ).model_dump(mode="json")

    if rtype in ("expense", "report", "slack"):
        results["budget"] = analyze_budget(
            BudgetInput(statements=statements, budget_targets=None)
        ).model_dump(mode="json")
        results["anomalies"] = detect_anomalies(
            AnomalyInput(statements=statements)
        ).model_dump(mode="json")

    state["tool_results"] = results
    return state


def route_to_model(state: AgentState) -> Literal["opus_node", "sonnet_node", "haiku_node"]:
    """Conditional edge: select which LLM node to run."""
    task_type = _infer_task_type(state)
    model = select_model(task_type)

    if "opus" in model:
        return "opus_node"
    if "haiku" in model:
        return "haiku_node"
    return "sonnet_node"


def _configure_dspy(model_id: str) -> None:
    """Configure DSPy to use the given Anthropic model."""
    import os
    lm = dspy.LM(f"anthropic/{model_id}", api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    dspy.configure(lm=lm)


def _run_dspy_analysis(state: AgentState, model_id: str) -> AgentState:
    """Common logic: configure DSPy, run the appropriate module, store output."""
    from backend.app.agents.financial_reporting import FinancialReportGenerator
    from backend.app.agents.cashflow import CashflowAnalyzer
    from backend.app.agents.expense import ExpenseSummarizer, StrategicAnalyzer

    _configure_dspy(model_id)

    rtype = state["request_type"]
    tool_results = state.get("tool_results", {})
    params = state.get("request_params", {})

    if rtype == "report":
        module = FinancialReportGenerator()
        result = module.forward(tool_results=tool_results, financial_data=state.get("financial_data") or {})
        analysis = result.report
    elif rtype == "cashflow":
        module = CashflowAnalyzer()
        result = module.forward(tool_results=tool_results, months=params.get("months", 6))
        analysis = result.narrative
    elif rtype == "expense":
        module = ExpenseSummarizer()
        result = module.forward(tool_results=tool_results)
        analysis = result.summary
    elif rtype == "slack":
        task_type = _infer_task_type(state)
        question = params.get("question", "")
        if task_type == "strategic_recommendation":
            module = StrategicAnalyzer()
            result = module.forward(
                tool_results=tool_results,
                financial_data=state.get("financial_data") or {},
                user_question=question,
            )
            analysis = result.analysis
        else:
            module = CashflowAnalyzer()
            result = module.forward(tool_results=tool_results, months=3)
            analysis = getattr(result, "narrative", str(result))
    else:
        analysis = "Analysis not available for this request type."

    state["model_used"] = model_id
    state["llm_analysis"] = analysis
    state["llm_numbers"] = {}
    return state


def opus_node(state: AgentState) -> AgentState:
    return _run_dspy_analysis(state, "claude-opus-4-20250514")


def sonnet_node(state: AgentState) -> AgentState:
    return _run_dspy_analysis(state, "claude-sonnet-4-5-20250514")


def haiku_node(state: AgentState) -> AgentState:
    return _run_dspy_analysis(state, "claude-haiku-4-5-20250301")


def cross_validate_node(state: AgentState) -> AgentState:
    """Compare LLM numeric outputs against tool outputs. Tools always win."""
    from decimal import Decimal
    tool_results = state.get("tool_results", {})
    llm_text = state.get("llm_analysis", "")

    # Build flat dict of key tool numbers for validation
    tool_numbers: dict[str, Decimal] = {}
    runway = tool_results.get("runway", {})
    if runway:
        burn = runway.get("monthly_burn_rate")
        if burn is not None:
            tool_numbers["burn_rate"] = Decimal(str(burn))
        rm = runway.get("runway_months")
        if rm is not None:
            tool_numbers["runway_months"] = Decimal(str(rm))

    ratios = tool_results.get("ratios", {})
    for key in ("gross_margin", "net_margin", "current_ratio"):
        val = ratios.get(key)
        if val is not None:
            tool_numbers[key] = Decimal(str(val))

    validator_result = cross_validate(tool_numbers, llm_text)
    state["discrepancies"] = [d.model_dump(mode="json") for d in validator_result.discrepancies]
    return state


def format_output(state: AgentState) -> AgentState:
    """Assemble final output dict from tool results and LLM analysis."""
    state["output"] = {
        "tool_results": state.get("tool_results", {}),
        "analysis": state.get("llm_analysis", ""),
        "model_used": state.get("model_used", ""),
        "discrepancies": state.get("discrepancies", []),
        "cache_hit": state.get("cache_hit", False),
    }
    return state


# ---------------------------------------------------------------------------
# Build the graph
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("fetch_data", fetch_financial_data)
    graph.add_node("run_tools", run_deterministic_tools)
    graph.add_node("opus_node", opus_node)
    graph.add_node("sonnet_node", sonnet_node)
    graph.add_node("haiku_node", haiku_node)
    graph.add_node("cross_validate", cross_validate_node)
    graph.add_node("format_output", format_output)

    graph.add_edge(START, "fetch_data")
    graph.add_edge("fetch_data", "run_tools")
    graph.add_conditional_edges(
        "run_tools",
        route_to_model,
        {
            "opus_node": "opus_node",
            "sonnet_node": "sonnet_node",
            "haiku_node": "haiku_node",
        },
    )
    graph.add_edge("opus_node", "cross_validate")
    graph.add_edge("sonnet_node", "cross_validate")
    graph.add_edge("haiku_node", "cross_validate")
    graph.add_edge("cross_validate", "format_output")
    graph.add_edge("format_output", END)

    return graph


# Compiled graph — import this in API endpoints
compiled_graph = build_graph().compile()
