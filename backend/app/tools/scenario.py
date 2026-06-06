from decimal import Decimal
from langchain_core.tools import tool
from backend.app.tools.schemas import FinancialSummary, ScenarioChange, ScenarioResult
from backend.app.tools.burn_rate import calculate_burn_rate
from backend.app.tools.runway import calculate_runway

@tool
def calculate_scenario_impact(summary: FinancialSummary, changes: list[ScenarioChange]) -> ScenarioResult:
    """
    Simulates what-if outcomes by analyzing the immediate impact of hiring, 
    firing, or revenue events on the current runway and burn rate.
    Positive monthly_impact values denote increased costs/worse burn.
    Negative monthly_impact values denote savings/increased revenue matching improved burn.
    """
    # Guard: no financial data
    if not summary.monthly_financials:
        current_burn = Decimal("0")
        gross_burn = Decimal("0")
        total_impact = Decimal("0")
        for change in changes:
            total_impact += change.monthly_impact
            if change.pct_of_burn is not None:
                total_impact += current_burn * change.pct_of_burn
            if change.pct_of_expenses is not None:
                total_impact += -(gross_burn * abs(change.pct_of_expenses))
        cash = summary.current_cash_balance
        if total_impact <= Decimal("0"):
            new_runway = Decimal("9999")
        elif cash <= Decimal("0"):
            new_runway = Decimal("0")
        else:
            new_runway = (cash / total_impact).quantize(Decimal("0.01"))
        return ScenarioResult(
            current_runway=Decimal("9999"),
            new_runway=new_runway,
            delta_runway=new_runway - Decimal("9999"),
            current_burn=Decimal("0"),
            new_burn=total_impact,
            delta_burn=total_impact,
            changes_applied=changes,
        )

    # 1. Establish the baseline
    base_burn = calculate_burn_rate.invoke({"summary": summary})
    base_runway = calculate_runway.invoke({"summary": summary, "burn_rate": base_burn})
    
    current_burn = base_burn.net_burn_monthly
    current_runway_months = base_runway.runway_months

    # 2. Iterate the changes array to compute the net deviation
    new_burn = current_burn
    for change in changes:
        new_burn += change.monthly_impact
        if change.pct_of_burn is not None:
            change_impact = current_burn * change.pct_of_burn
            new_burn += change_impact
        if change.pct_of_expenses is not None:
            gross_burn = base_burn.gross_burn_monthly
            change_impact = -(gross_burn * abs(change.pct_of_expenses))
            new_burn += change_impact

    # 3. Simulate new projected runway
    cash = summary.current_cash_balance
    if new_burn <= Decimal("0"):
        new_runway_months = Decimal("9999")  # Infinite runway marker
    else:
        new_runway_months = cash / new_burn
        new_runway_months = new_runway_months.quantize(Decimal("0.01"))
        
    delta_runway = new_runway_months - current_runway_months
    delta_burn = new_burn - current_burn

    return ScenarioResult(
        current_runway=current_runway_months,
        new_runway=new_runway_months,
        delta_runway=delta_runway,
        current_burn=current_burn,
        new_burn=new_burn,
        delta_burn=delta_burn,
        changes_applied=changes
    )
