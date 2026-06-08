from decimal import Decimal
from backend.app.tools.anomaly import calculate_anomalies
from backend.app.tools.scenario import calculate_scenario_impact
from backend.app.tools.fundraising import calculate_fundraising_readiness
from backend.app.tools.schemas import ScenarioChange

def test_calculate_anomalies_success(profile_with_anomaly):
    result = calculate_anomalies.invoke({"summary": profile_with_anomaly})
    
    assert result.scan_period_months == 3
    assert len(result.anomalies) == 1
    
    anomaly = result.anomalies[0]
    assert anomaly.category == "AWS"
    assert anomaly.severity == "critical"
    assert anomaly.z_score > Decimal("3.0")

def test_calculate_anomalies_empty(profile_new):
    result = calculate_anomalies.invoke({"summary": profile_new})
    assert len(result.anomalies) == 0

def test_calculate_scenario_impact(profile_healthy):
    changes = [
        ScenarioChange(type="hire", description="Hire 2 developers", monthly_impact=Decimal("24000"))
    ]
    
    res = calculate_scenario_impact.invoke({"summary": profile_healthy, "changes": changes})
    
    assert res.delta_burn == Decimal("24000")
    assert res.new_burn > res.current_burn
    assert res.new_runway < res.current_runway 
    assert res.new_runway > Decimal("10")
    assert len(res.changes_applied) == 1

def test_calculate_fundraising_readiness_healthy(profile_healthy):
    res = calculate_fundraising_readiness.invoke({"summary": profile_healthy})
    
    assert res.metrics.mrr == Decimal("22000")
    assert res.metrics.arr == Decimal("264000")
    assert res.metrics.mrr_growth_rate == Decimal("10.00")
    assert res.readiness_score > 0
    assert len(res.gaps) > 0 

def test_calculate_fundraising_pre_revenue(profile_pre_revenue):
    res = calculate_fundraising_readiness.invoke({"summary": profile_pre_revenue})
    
    assert res.metrics.mrr == Decimal("0")
    assert res.metrics.arr == Decimal("0")
    assert res.readiness_score < 40 
    assert any("Pre-revenue startups face harder hurdles" in gap for gap in res.gaps)

def test_calculate_anomalies_flat_spike():
    from backend.app.tools.schemas import FinancialSummary, MonthlyFinancial
    from datetime import date
    summary = FinancialSummary(
        current_cash_balance=Decimal("100000"),
        monthly_financials=[
            MonthlyFinancial(month_start=date(2025, 1, 1), total_revenue=Decimal("10000"), total_expenses=Decimal("5000"), net_income=Decimal("5000"), category_expenses={"Software": Decimal("100")}),
            MonthlyFinancial(month_start=date(2025, 2, 1), total_revenue=Decimal("10000"), total_expenses=Decimal("5000"), net_income=Decimal("5000"), category_expenses={"Software": Decimal("100")}),
            MonthlyFinancial(month_start=date(2025, 3, 1), total_revenue=Decimal("10000"), total_expenses=Decimal("6000"), net_income=Decimal("4000"), category_expenses={"Software": Decimal("2000")}),
        ]
    )
    result = calculate_anomalies.invoke({"summary": summary})
    assert len(result.anomalies) == 1
    assert result.anomalies[0].category == "Software"
    assert result.anomalies[0].z_score > Decimal("10.0")

def test_calculate_anomalies_warning_range(profile_with_anomaly):
    from backend.app.tools.schemas import FinancialSummary, MonthlyFinancial
    from datetime import date
    summary = FinancialSummary(
        current_cash_balance=Decimal("100000"),
        monthly_financials=[
            MonthlyFinancial(month_start=date(2025, 1, 1), total_revenue=Decimal("10000"), total_expenses=Decimal("5000"), net_income=Decimal("5000"), category_expenses={"Office": Decimal("1000")}),
            MonthlyFinancial(month_start=date(2025, 2, 1), total_revenue=Decimal("10000"), total_expenses=Decimal("5000"), net_income=Decimal("5000"), category_expenses={"Office": Decimal("1000")}),
            MonthlyFinancial(month_start=date(2025, 3, 1), total_revenue=Decimal("10000"), total_expenses=Decimal("5000"), net_income=Decimal("5000"), category_expenses={"Office": Decimal("1500")}),
            MonthlyFinancial(month_start=date(2025, 4, 1), total_revenue=Decimal("10000"), total_expenses=Decimal("5000"), net_income=Decimal("5000"), category_expenses={"Office": Decimal("500")}),
            MonthlyFinancial(month_start=date(2025, 5, 1), total_revenue=Decimal("10000"), total_expenses=Decimal("6000"), net_income=Decimal("4000"), category_expenses={"Office": Decimal("2000")}),
        ]
    )
    result = calculate_anomalies.invoke({"summary": summary})
    assert len(result.anomalies) == 1
    assert result.anomalies[0].severity == "warning"

def test_calculate_anomalies_flat_no_spike():
    from backend.app.tools.schemas import FinancialSummary, MonthlyFinancial
    from datetime import date
    summary = FinancialSummary(
        current_cash_balance=Decimal("100000"),
        monthly_financials=[
            MonthlyFinancial(month_start=date(2025, 1, 1), total_revenue=Decimal("10000"), total_expenses=Decimal("5000"), net_income=Decimal("5000"), category_expenses={"Software": Decimal("100")}),
            MonthlyFinancial(month_start=date(2025, 2, 1), total_revenue=Decimal("10000"), total_expenses=Decimal("5000"), net_income=Decimal("5000"), category_expenses={"Software": Decimal("100")}),
            MonthlyFinancial(month_start=date(2025, 3, 1), total_revenue=Decimal("10000"), total_expenses=Decimal("5000"), net_income=Decimal("5000"), category_expenses={"Software": Decimal("100")}),
        ]
    )
    result = calculate_anomalies.invoke({"summary": summary})
    assert len(result.anomalies) == 0

def test_scenario_infinite_runway():
    from backend.app.tools.schemas import FinancialSummary, MonthlyFinancial
    from datetime import date
    summary = FinancialSummary(
        current_cash_balance=Decimal("100000"),
        monthly_financials=[
            MonthlyFinancial(month_start=date(2025, 1, 1), total_revenue=Decimal("10000"), total_expenses=Decimal("5000"), net_income=Decimal("5000"), category_expenses={}),
            MonthlyFinancial(month_start=date(2025, 2, 1), total_revenue=Decimal("10000"), total_expenses=Decimal("5000"), net_income=Decimal("5000"), category_expenses={}),
        ]
    )
    changes = [ScenarioChange(type="revenue_change", description="Massive rev", monthly_impact=Decimal("-50000"))]
    res = calculate_scenario_impact.invoke({"summary": summary, "changes": changes})
    assert res.new_runway == Decimal("9999")


def test_calculate_anomalies_multi_month_spike():
    from backend.app.tools.schemas import FinancialSummary, MonthlyFinancial
    from datetime import date
    summary = FinancialSummary(
        current_cash_balance=Decimal("100000"),
        monthly_financials=[
            MonthlyFinancial(month_start=date(2025, 1, 1), total_revenue=Decimal("10000"), total_expenses=Decimal("5000"), net_income=Decimal("5000"), category_expenses={"AWS": Decimal("500")}),
            MonthlyFinancial(month_start=date(2025, 2, 1), total_revenue=Decimal("10000"), total_expenses=Decimal("5000"), net_income=Decimal("5000"), category_expenses={"AWS": Decimal("500")}),
            MonthlyFinancial(month_start=date(2025, 3, 1), total_revenue=Decimal("10000"), total_expenses=Decimal("15000"), net_income=Decimal("-5000"), category_expenses={"AWS": Decimal("10500")}),
            MonthlyFinancial(month_start=date(2025, 4, 1), total_revenue=Decimal("10000"), total_expenses=Decimal("5000"), net_income=Decimal("5000"), category_expenses={"AWS": Decimal("500")}),
            MonthlyFinancial(month_start=date(2025, 5, 1), total_revenue=Decimal("10000"), total_expenses=Decimal("5000"), net_income=Decimal("5000"), category_expenses={"AWS": Decimal("500")}),
        ]
    )
    result = calculate_anomalies.invoke({"summary": summary})
    assert len(result.anomalies) == 1
    anomaly = result.anomalies[0]
    assert anomaly.category == "AWS"
    assert anomaly.month == "Mar 2025"
    assert "Mar 2025" in anomaly.description


def test_calculate_anomalies_fallback_spike():
    from backend.app.tools.schemas import FinancialSummary, MonthlyFinancial
    from datetime import date
    summary = FinancialSummary(
        current_cash_balance=Decimal("100000"),
        monthly_financials=[
            MonthlyFinancial(month_start=date(2025, 1, 1), total_revenue=Decimal("10000"), total_expenses=Decimal("10000"), net_income=Decimal("0"), category_expenses={"Software & Cloud": Decimal("1000")}),
            MonthlyFinancial(month_start=date(2025, 2, 1), total_revenue=Decimal("10000"), total_expenses=Decimal("10000"), net_income=Decimal("0"), category_expenses={"Software & Cloud": Decimal("10000")}),
            MonthlyFinancial(month_start=date(2025, 3, 1), total_revenue=Decimal("10000"), total_expenses=Decimal("10000"), net_income=Decimal("0"), category_expenses={"Software & Cloud": Decimal("1000")}),
            MonthlyFinancial(month_start=date(2025, 4, 1), total_revenue=Decimal("10000"), total_expenses=Decimal("20000"), net_income=Decimal("-10000"), category_expenses={"Software & Cloud": Decimal("12000")}),
            MonthlyFinancial(month_start=date(2025, 5, 1), total_revenue=Decimal("10000"), total_expenses=Decimal("10000"), net_income=Decimal("0"), category_expenses={"Software & Cloud": Decimal("1000")}),
        ]
    )
    result = calculate_anomalies.invoke({"summary": summary})
    assert len(result.anomalies) == 1
    anomaly = result.anomalies[0]
    assert anomaly.category == "Software & Cloud"
    assert anomaly.month == "Apr 2025"
    assert "Apr 2025" in anomaly.description

