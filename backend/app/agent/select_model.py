from langchain_core.messages import HumanMessage
from backend.app.agent.state import AgentState

def route_query_complexity(state: AgentState) -> dict:
    messages = state["messages"]
    if not messages:
        return {"recommended_model": "claude-haiku-4-5-20250301"}
        
    last_msg = messages[-1]
    if not isinstance(last_msg, HumanMessage):
        return {"recommended_model": "claude-sonnet-4-5-20250514"}
        
    content = str(last_msg.content).lower()
    
    opus_keywords = ["what if", "scenario", "simulate", "if i hire", "if we fire", "fundraising strategy", "investor readiness"]
    if any(k in content for k in opus_keywords):
        return {"recommended_model": "claude-opus-4-6-20250514"}
        
    haiku_keywords = ["hi", "hello", "hey", "who are you", "what can you do"]
    if any(k in content for k in haiku_keywords) and len(content.split()) < 10:
        return {"recommended_model": "claude-haiku-4-5-20250301"}
        
    return {"recommended_model": "claude-sonnet-4-5-20250514"}