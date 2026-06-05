from langchain_core.messages import HumanMessage
from backend.app.agent.state import AgentState

def route_query_complexity(state: AgentState) -> dict:
    messages = state["messages"]
    if not messages:
        return {"recommended_model": "claude-haiku-4-5-20251001"}
        
    last_msg = messages[-1]
    if not isinstance(last_msg, HumanMessage):
        return {"recommended_model": "claude-sonnet-4-6"}
        
    content = str(last_msg.content).lower()
    
    opus_keywords = [
        "what if", "scenario", "simulate", 
        "if i hire", "if we fire", 
        "fundraising strategy", "investor readiness"
    ]

    sonnet_keywords = [
        "report", "full", "analysis", "explain", 
        "why", "compare", "breakdown", "forecast",
        "am i ready", "should i", "anomal"
    ]

    haiku_keywords_greeting = ["hi", "hello", "hey", "who are you", "what can you do"]

    # Opus: complex reasoning and scenario
    if any(k in content for k in opus_keywords):
        return {"recommended_model": "claude-opus-4-8"}

    # Haiku: greeting OR single-metric simple question
    if any(k in content for k in haiku_keywords_greeting) and len(content.split()) < 10:
        return {"recommended_model": "claude-haiku-4-5-20251001"}

    simple_financial = ["burn rate", "runway", "cash balance", "what is my", "how much"]
    if any(k in content for k in simple_financial) and not any(k in content for k in sonnet_keywords):
        return {"recommended_model": "claude-haiku-4-5-20251001"}

    # Sonnet: reports, analysis, complex explanation
    if any(k in content for k in sonnet_keywords):
        return {"recommended_model": "claude-sonnet-4-6"}

    # Default: sonnet
    return {"recommended_model": "claude-sonnet-4-6"}