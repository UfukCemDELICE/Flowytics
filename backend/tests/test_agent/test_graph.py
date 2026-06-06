from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from backend.app.agent.select_model import route_query_complexity
from backend.app.agent.cross_validate import cross_validate_math, validation_edge
from backend.app.agent.graph import should_continue

def test_route_query_complexity():
    # Haiku Triggers (Greetings)
    state = {"messages": [HumanMessage(content="Hello!")]}
    res = route_query_complexity({"messages": [HumanMessage(content="Hello")]})
    assert res["recommended_model"] == "claude-haiku-4-5-20251001"
    
    # Opus Triggers (Deep Scenarios)
    state2 = {"messages": [HumanMessage(content="simulate what happens if we fire 5 people")]}
    res2 = route_query_complexity({"messages": [HumanMessage(content="What if i hire 2 people?")]})
    assert res2["recommended_model"] == "claude-opus-4-8"
    
    # Haiku Triggers (Simple Financial without Sonnet keywords)
    res3 = route_query_complexity({"messages": [HumanMessage(content="Show me my runway")]})
    assert res3["recommended_model"] == "claude-haiku-4-5-20251001"
    
    res_arr = route_query_complexity({"messages": [HumanMessage(content="What is my ARR?")]})
    assert res_arr["recommended_model"] == "claude-haiku-4-5-20251001"

    res_run_rate = route_query_complexity({"messages": [HumanMessage(content="run rate")]})
    assert res_run_rate["recommended_model"] == "claude-haiku-4-5-20251001"

    # Sonnet Triggers (Analysis/Explain/Forecast etc.)
    res4 = route_query_complexity({"messages": [HumanMessage(content="Explain my burn rate")]})
    assert res4["recommended_model"] == "claude-sonnet-4-6"

    # Default (Fallback to Sonnet)
    res_default = route_query_complexity({"messages": [HumanMessage(content="Explain general startup trends for 2026")]})
    assert res_default["recommended_model"] == "claude-sonnet-4-6"

def test_should_continue():
    # State containing LLM output mapping directly to Python function calls
    ai_call = AIMessage(content="", tool_calls=[{"name": "some_tool", "args": {}, "id": "1"}])
    state = {"messages": [ai_call]}
    
    # Expect Edge Router -> "tools"
    assert should_continue(state) == "tools"
    
    # State containing LLM pure text generation matching an end state
    ai_answer = AIMessage(content="Here is your answer.")
    state2 = {"messages": [ai_answer]}
    
    # Expect Edge Router -> "end"
    assert should_continue(state2) == "end"

def test_cross_validate_math_clean():
    # Tool generates 12.5 months runway
    tool_msg = ToolMessage(content='{"runway_months": "12.5"}', tool_call_id="1")
    # AI accurately reports 12.5
    ai_msg = AIMessage(content="Your runway is sitting exactly at 12.5 months.")
    state = {"messages": [tool_msg, ai_msg]}
    
    res = cross_validate_math(state)
    
    # No corrections generated
    assert len(res["messages"]) == 0
    
    # Edge validates passing cleanly to END
    edge = validation_edge(state)
    assert edge == "end"

def test_cross_validate_math_hallucination():
    # Tool computes cleanly
    tool_msg = ToolMessage(content='{"runway_months": "12.5"}', tool_call_id="2")
    # AI hallucinates completely different digits
    ai_msg = AIMessage(content="Your runway is massive at 24.0 months!")
    state = {"messages": [tool_msg, ai_msg]}
    
    res = cross_validate_math(state)
    
    # Must intercept and throw a hidden System Validator message back into the LangGraph loop
    assert len(res["messages"]) == 1
    assert isinstance(res["messages"][0], HumanMessage)
    assert "24.0" in res["messages"][0].content
    assert res["messages"][0].name == "system_validator"
    
    # Simulate StateGraph advancing with injected Correction Prompts
    state["messages"].append(res["messages"][0])
    edge = validation_edge(state)
    assert edge == "needs_correction"

def test_cross_validate_ignores_years():
    tool_msg = ToolMessage(content='{"runway_months": "12.5"}', tool_call_id="3")
    # AI uses structural text integers (2025) that are not natively returned by the tool JSON array.
    ai_msg = AIMessage(content="In 2025, your runway will be 12.5 months.")
    state = {"messages": [tool_msg, ai_msg]}
    
    res = cross_validate_math(state)
    # 2025 should be whitelisted gracefully
    assert len(res["messages"]) == 0
