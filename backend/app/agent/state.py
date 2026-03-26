from typing import Annotated, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from backend.app.tools.schemas import FinancialSummary

class AgentState(TypedDict):
    """
    The core state object for the Flowytics LangGraph execution loop.
    Maintains conversational memory, active financial data context, arrays of tool outputs,
    and routing variables across iterative graph nodes.
    """
    messages: Annotated[list[BaseMessage], add_messages]
    financial_summary: FinancialSummary
    recommended_model: str | None
