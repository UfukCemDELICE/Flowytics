from langchain_core.messages import HumanMessage
from backend.app.agent.state import AgentState

def route_query_complexity(state: AgentState) -> dict:
    """
    Inspects the last user message and determines the optimal Claude model tier.
    Used as an entry-point node to optimize LLM latency and costs.
    Updates the 'recommended_model' state variable.
    """
    messages = state["messages"]
    if not messages:
        return {"recommended_model": "claude-4-5-haiku-latest"}
        
    last_msg = messages[-1]
    # If the last message isn't from the human, default to Sonnet
    if not isinstance(last_msg, HumanMessage):
        return {"recommended_model": "claude-4-6-sonnet-latest"}
        
    content = str(last_msg.content).lower()
    
    # 1. Opus Triggers (Deep Scenarios, Matrix What-ifs, High-stakes Strategy)
    opus_keywords = ["what if", "scenario", "simulate", "if i hire", "if we fire", "fundraising strategy", "investor readiness"]
    if any(k in content for k in opus_keywords):
        return {"recommended_model": "claude-4-6-opus-latest"}
        
    # 2. Haiku Triggers (Simple Greetings, Basic Support)
    haiku_keywords = ["hi", "hello", "hey", "who are you", "what can you do"]
    if any(k in content for k in haiku_keywords) and len(content.split()) < 10:
        return {"recommended_model": "claude-4-5-haiku-latest"}
        
    # 3. Sonnet Triggers (Standard Data Reports, Analytics, Anomalies, Runways)
    return {"recommended_model": "claude-4-6-sonnet-latest"}
