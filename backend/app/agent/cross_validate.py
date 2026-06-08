# DISABLED: replaced by authoritative-data injection in custom_tool_node. Kept for reference; produced false positives (flagged legitimate tool numbers as hallucinations).
import re
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from backend.app.agent.state import AgentState

def cross_validate_math(state: AgentState) -> dict:
    """
    LangGraph Safety Node. 
    Strictly compares numeric values generated in the final AIMessage text 
    against the exact raw structural numeric outputs produced by the ToolMessages.
    
    If the LLM hallucinates external values, it injects a hidden system prompt 
    demanding an immediate recalculation.
    """
    messages = state["messages"]
    if not messages:
        return {"messages": []}
        
    # Fetch the most recent AIMessage
    ai_messages = [m for m in messages if isinstance(m, AIMessage)]
    if not ai_messages:
        return {"messages": []}
        
    last_ai_msg = ai_messages[-1]
    
    # If the LLM is still trying to call tools, we don't validate conversational math yet
    if getattr(last_ai_msg, "tool_calls", None):
        return {"messages": []}
        
    # Pull all the Tool outputs it consumed
    tool_messages = [m for m in messages if isinstance(m, ToolMessage)]
    if not tool_messages:
        return {"messages": []}
        
    # Extract structural integers and decimals (ignoring single digits 0-9 for pure linguistic usage)
    ai_text = str(last_ai_msg.content)
    ai_numbers = re.findall(r'\b\d{2,}(?:\.\d+)?\b', ai_text)
    
    # Dump all JSON outputs from tools
    tool_data_dump = " ".join([str(m.content) for m in tool_messages])
    tool_numbers = set(re.findall(r'\b\d{2,}(?:\.\d+)?\b', tool_data_dump))
    
    hallucinations = []
    
    for num_str in ai_numbers:
        # Ignore years common in conversation (e.g. 2025, 2026)
        if num_str.startswith("202") and len(num_str) == 4:
            continue
            
        if num_str not in tool_numbers:
            hallucinations.append(num_str)
            
    if hallucinations:
        # Math deviation detected. Force LangGraph to loop back and try again.
        correction_prompt = (
            f"SYSTEM SAFETY FILTER: You generated the following numbers which were NOT present "
            f"in the tool outputs: {list(set(hallucinations))}. "
            f"You MUST NOT hallucinate mathematical values. Re-read the tool outputs strictly and correct your response."
        )
        return {"messages": [HumanMessage(content=correction_prompt, name="system_validator")]}
        
    # Math is clean, pass silently
    return {"messages": []}

def validation_edge(state: AgentState) -> str:
    """
    LangGraph Conditional Edge mapping logic.
    If the cross-validator triggered a correction message, route back to the LLM.
    Otherwise, terminate execution gracefully.
    """
    messages = state["messages"]
    last_msg = messages[-1]
    
    if isinstance(last_msg, HumanMessage) and last_msg.name == "system_validator":
        return "needs_correction"
        
    return "end"
