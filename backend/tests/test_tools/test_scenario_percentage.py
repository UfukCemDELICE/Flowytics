from decimal import Decimal
from backend.app.tools.burn_rate import calculate_burn_rate
from backend.app.tools.scenario import calculate_scenario_impact
from backend.app.tools.schemas import ScenarioChange

def test_scenario_positive_burn_percentage(profile_healthy):
    base_burn = calculate_burn_rate.invoke({"summary": profile_healthy})
    base_net_burn = base_burn.net_burn_monthly
    assert base_net_burn > Decimal("0")
    
    changes = [
        ScenarioChange(
            type="cut_expense",
            description="Cut net burn by 20%",
            pct_of_burn=Decimal("-0.20")
        )
    ]
    
    res = calculate_scenario_impact.invoke({"summary": profile_healthy, "changes": changes})
    
    assert res.current_burn == base_net_burn
    assert round(res.new_burn, 4) == round(base_net_burn * Decimal("0.80"), 4)
    assert round(res.delta_burn, 4) == round(base_net_burn * Decimal("-0.20"), 4)
    assert res.new_runway > res.current_runway

def test_scenario_negative_burn_percentage(profile_profitable):
    base_burn = calculate_burn_rate.invoke({"summary": profile_profitable})
    base_net_burn = base_burn.net_burn_monthly
    assert base_net_burn < Decimal("0")
    
    changes = [
        ScenarioChange(
            type="cut_expense",
            description="Reduce burn by 20%",
            pct_of_burn=Decimal("-0.20")
        )
    ]
    
    res = calculate_scenario_impact.invoke({"summary": profile_profitable, "changes": changes})
    
    assert res.current_burn == base_net_burn
    assert round(res.new_burn, 4) == round(base_net_burn * Decimal("0.80"), 4)
    assert round(res.delta_burn, 4) == round(base_net_burn * Decimal("-0.20"), 4)
    assert res.new_runway == Decimal("9999")
    assert res.current_runway == Decimal("9999")
    assert res.delta_runway == Decimal("0")

def test_scenario_both_impact_and_percentage(profile_healthy):
    base_burn = calculate_burn_rate.invoke({"summary": profile_healthy})
    base_net_burn = base_burn.net_burn_monthly
    
    changes = [
        ScenarioChange(
            type="cut_expense",
            description="Cut by 20% and add $1000",
            pct_of_burn=Decimal("-0.20"),
            monthly_impact=Decimal("1000")
        )
    ]
    
    res = calculate_scenario_impact.invoke({"summary": profile_healthy, "changes": changes})
    
    expected_new_burn = base_net_burn + Decimal("1000") + (base_net_burn * Decimal("-0.20"))
    assert round(res.new_burn, 4) == round(expected_new_burn, 4)
    assert round(res.delta_burn, 4) == round(res.new_burn - base_net_burn, 4)

def test_scenario_positive_burn_pct_of_expenses(profile_healthy):
    base_burn = calculate_burn_rate.invoke({"summary": profile_healthy})
    base_net_burn = base_burn.net_burn_monthly
    base_gross_burn = base_burn.gross_burn_monthly
    assert base_net_burn > Decimal("0")
    assert base_gross_burn > Decimal("0")
    
    changes = [
        ScenarioChange(
            type="cut_expense",
            description="Cut expenses by 20%",
            pct_of_expenses=Decimal("-0.20")
        )
    ]
    
    res = calculate_scenario_impact.invoke({"summary": profile_healthy, "changes": changes})
    
    expected_new_burn = base_net_burn - (base_gross_burn * Decimal("0.20"))
    assert res.current_burn == base_net_burn
    assert round(res.new_burn, 4) == round(expected_new_burn, 4)
    assert round(res.delta_burn, 4) == round(-(base_gross_burn * Decimal("0.20")), 4)

def test_scenario_negative_burn_pct_of_expenses(profile_profitable):
    base_burn = calculate_burn_rate.invoke({"summary": profile_profitable})
    base_net_burn = base_burn.net_burn_monthly
    base_gross_burn = base_burn.gross_burn_monthly
    assert base_net_burn < Decimal("0")
    assert base_gross_burn > Decimal("0")
    
    changes = [
        ScenarioChange(
            type="cut_expense",
            description="Cut expenses by 20%",
            pct_of_expenses=Decimal("-0.20")
        )
    ]
    
    res = calculate_scenario_impact.invoke({"summary": profile_profitable, "changes": changes})
    
    expected_new_burn = base_net_burn - (base_gross_burn * Decimal("0.20"))
    assert res.current_burn == base_net_burn
    assert round(res.new_burn, 4) == round(expected_new_burn, 4)
    assert res.new_burn < base_net_burn  # Moves more negative (more profitable)
    assert res.new_runway == Decimal("9999")

