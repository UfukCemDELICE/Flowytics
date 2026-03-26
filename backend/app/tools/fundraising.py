from decimal import Decimal
from langchain_core.tools import tool
from backend.app.tools.schemas import FinancialSummary, FundraisingResult, FundraisingMetrics
from backend.app.tools.burn_rate import calculate_burn_rate
from backend.app.tools.runway import calculate_runway

@tool
def calculate_fundraising_readiness(summary: FinancialSummary) -> FundraisingResult:
    """
    Analyzes historical startup financials to calculate investor readiness metrics
    and generates a score out of 100 based on standard seed/series-A benchmarks.
    """
    financials = sorted(summary.monthly_financials, key=lambda x: x.month_start)
    if not financials:
        return FundraisingResult(
            readiness_score=0, 
            metrics=FundraisingMetrics(mrr=None, mrr_growth_rate=None, arr=None, burn_multiple=None, runway_months=Decimal("0"), gross_margin=None), 
            gaps=["No financial history found."]
        )

    recent = financials[-1]
    prev = financials[-2] if len(financials) > 1 else None
    
    mrr = recent.total_revenue
    arr = mrr * Decimal("12")
    
    # Calculate Month-Over-Month growth
    if prev and prev.total_revenue > Decimal("0"):
        mrr_growth_rate = ((mrr - prev.total_revenue) / prev.total_revenue) * Decimal("100")
        mrr_growth_rate = mrr_growth_rate.quantize(Decimal("0.01"))
    else:
        mrr_growth_rate = Decimal("0.00") if prev else None

    # Calculate Runway
    burn_result = calculate_burn_rate.invoke({"summary": summary})
    runway_res = calculate_runway.invoke({"summary": summary, "burn_rate": burn_result})
    runway_months = runway_res.runway_months
    
    # Calculate Capital Efficiency (Burn Multiple = Net Burn / Net New ARR)
    net_burn = burn_result.net_burn_monthly
    
    if prev and mrr_growth_rate and mrr_growth_rate > Decimal("0"):
        net_new_arr = (mrr - prev.total_revenue) * Decimal("12")
        burn_multiple = net_burn / net_new_arr if net_new_arr > 0 else Decimal("99.9")
        burn_multiple = burn_multiple.quantize(Decimal("0.01"))
    else:
        burn_multiple = None
        
    score = 0
    gaps = []
    
    # Evaluate Runway threshold checks
    if runway_months >= Decimal("6"):
        score += 25
    else:
        gaps.append(f"Runway is critically low ({runway_months} months). Investors expect to fund 18-24 months.")
        
    # Evaluate Growth threshold checks
    if mrr_growth_rate and mrr_growth_rate >= Decimal("15"):
        score += 25
    else:
        growth_str = f"{mrr_growth_rate}%" if mrr_growth_rate is not None else "Unknown"
        gaps.append(f"MoM growth is '{growth_str}'. Seed investors target > 15% for rapid scaling evidence.")
        
    # Evaluate Efficiency threshold checks
    if burn_multiple and burn_multiple <= Decimal("2.0"):
        score += 20
    else:
        burn_str = f"{burn_multiple}x" if burn_multiple is not None else "Unknown"
        gaps.append(f"Burn multiple is '{burn_str}'. Target < 2.0x to prove capital efficiency.")
        
    # Baseline existence of revenue
    if mrr > Decimal("0"):
        score += 15
        if mrr_growth_rate and mrr_growth_rate > Decimal("0"):
            score += 15 # Double reward for positive scaling
    else:
        gaps.append("Pre-revenue startups face harder hurdles; focus firmly on product-market validation and runway conservation.")

    return FundraisingResult(
        readiness_score=score,
        metrics=FundraisingMetrics(
            mrr=mrr,
            mrr_growth_rate=mrr_growth_rate,
            arr=arr,
            burn_multiple=burn_multiple,
            runway_months=runway_months,
            gross_margin=None # MVP excludes COGS from raw QBO mappings
        ),
        gaps=gaps
    )
