import os
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode

from backend.app.agent.state import AgentState
from backend.app.agent.select_model import route_query_complexity
from backend.app.agent.cross_validate import cross_validate_math, validation_edge

from backend.app.tools.burn_rate import calculate_burn_rate
from backend.app.tools.runway import calculate_runway
from backend.app.tools.cash_forecast import calculate_cash_forecast
from backend.app.tools.anomaly import calculate_anomalies
from backend.app.tools.scenario import calculate_scenario_impact
from backend.app.tools.fundraising import calculate_fundraising_readiness
from backend.app.tools.monthly_report import generate_monthly_report_data
from backend.app.tools.run_rate import calculate_run_rate

active_tools = [
    calculate_burn_rate,
    calculate_runway,
    calculate_cash_forecast,
    calculate_anomalies,
    calculate_scenario_impact,
    calculate_fundraising_readiness,
    generate_monthly_report_data,
    calculate_run_rate
]

tool_node = ToolNode(active_tools)

def custom_tool_node(state: AgentState) -> dict:
    messages = state["messages"]
    if messages:
        last_msg = messages[-1]
        if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
            new_tool_calls = []
            for tc in last_msg.tool_calls:
                tc_copy = tc.copy()
                if "args" in tc_copy:
                    tc_copy["args"] = tc_copy["args"].copy()
                    if "summary" in tc_copy["args"]:
                        tc_copy["args"]["summary"] = state["financial_summary"]
                new_tool_calls.append(tc_copy)
            last_msg.tool_calls = new_tool_calls
    return tool_node.invoke(state)

def load_prompt(filename: str) -> str:
    """Reads the core CFO persona configuration from the file system."""
    prompt_path = os.path.join(os.path.dirname(__file__), "prompts", filename)
    if os.path.exists(prompt_path):
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""

def call_model(state: AgentState) -> dict:
    messages = state["messages"]
    model_name = state.get("recommended_model", "claude-sonnet-4-6")
    summary = state.get("financial_summary")
    
    llm = ChatAnthropic(model=model_name)
    llm_with_tools = llm.bind_tools(active_tools)
    
    # 1. Base Core Prompt
    system_text = load_prompt("system_base.txt")
    if summary:
        num_months = len(summary.monthly_financials)
        if num_months > 0:
            start_date = summary.monthly_financials[0].month_start
            end_date = summary.monthly_financials[-1].month_start
            
            if hasattr(start_date, "strftime"):
                date_range = f"{start_date.strftime('%B %Y')} to {end_date.strftime('%B %Y')}"
            else:
                date_range = f"{start_date} to {end_date}"
                
            latest_month = summary.monthly_financials[-1]
            if hasattr(latest_month.month_start, "strftime"):
                latest_month_name = latest_month.month_start.strftime('%B %Y')
            else:
                latest_month_name = str(latest_month.month_start)
                
            system_text += (
                f"\n\nCURRENT FINANCIAL CONTEXT:"
                f"\nCash Balance: ${summary.current_cash_balance:,.2f}"
                f"\nMonths of Data: {num_months}"
                f"\nDate Range: {date_range}"
                f"\nLatest Month ({latest_month_name}): Revenue ${latest_month.total_revenue:,.2f}, Net Income ${latest_month.net_income:,.2f}"
            )
        else:
            system_text += (
                f"\n\nCURRENT FINANCIAL CONTEXT:"
                f"\nCash Balance: ${summary.current_cash_balance:,.2f}"
                f"\nMonths of Data: 0"
            )
        
    # 2. Dynamic Injector (Save token bounds)
    recent_text = str([str(m.content) for m in messages[-3:]]).lower()
    
    if any(k in recent_text for k in ["what if", "scenario", "hire", "fire", "cut", "reduce", "drop", "%", "percent"]):
        system_text += "\n\n" + load_prompt("scenario.txt")
        
    if any(k in recent_text for k in ["anomaly", "spike", "unusual", "outlier"]):
        system_text += "\n\n" + load_prompt("anomaly.txt")
        
    if any(k in recent_text for k in ["fundraising", "investor", "raise", "seed"]):
        system_text += "\n\n" + load_prompt("fundraising.txt")
        
    system_msg = SystemMessage(content=system_text)
    
    filtered_messages = [m for m in messages if not isinstance(m, SystemMessage)]
    final_payload = [system_msg] + filtered_messages
        
    response = llm_with_tools.invoke(final_payload)
    return {"messages": [response]}

def should_continue(state: AgentState) -> str:
    messages = state["messages"]
    last_msg = messages[-1]
    if getattr(last_msg, "tool_calls", None):
        return "tools"
    return "end"

workflow = StateGraph(AgentState)

workflow.add_node("select_model", route_query_complexity)
workflow.add_node("agent", call_model)
workflow.add_node("tools", custom_tool_node)

workflow.add_edge(START, "select_model")
workflow.add_edge("select_model", "agent")
workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", "end": END})
workflow.add_edge("tools", "agent")

app = workflow.compile()
