import pytest
from backend.app.integrations.slack import SlackClient

def test_slack_client_block_formatting():
    client = SlackClient()
    
    # Test CFO Response Block
    text = "Runway is 5 months."
    cfo_blocks = client.format_cfo_response_block(text)
    
    assert len(cfo_blocks) == 2
    assert cfo_blocks[0]["type"] == "section"
    assert "Runway is 5 months" in cfo_blocks[0]["text"]["text"]
    assert cfo_blocks[1]["type"] == "context"
    
    # Test Proactive Alert Block
    alert_text = "Burn rate spiked by 30%."
    alert_blocks = client.format_proactive_alert_block(alert_text, severity="critical")
    
    assert len(alert_blocks) == 3
    assert alert_blocks[0]["type"] == "header"
    assert "🚨" in alert_blocks[0]["text"]["text"]
    assert alert_blocks[2]["type"] == "section"
    assert "Burn rate spiked" in alert_blocks[2]["text"]["text"]

def test_slack_agent_runner_import():
    # If this fails, we have an import cycle or syntax error in our agent runner
    try:
        from backend.app.services.slack_agent_runner import process_slack_message
        assert callable(process_slack_message)
    except Exception as e:
        pytest.fail(f"slack_agent_runner import failed: {e}")

def test_proactive_alerts_import():
    # If this fails, we have an import cycle or syntax error in our proactive alerts
    try:
        from backend.app.services.proactive_alerts import run_proactive_alerts
        assert callable(run_proactive_alerts)
    except Exception as e:
        pytest.fail(f"proactive_alerts import failed: {e}")
