from datetime import date
from decimal import Decimal
from langchain_core.tools import tool
from backend.app.tools.schemas import FinancialSummary, FundraisingResult, FundraisingMetrics
from backend.app.tools.burn_rate import calculate_burn_rate
from backend.app.tools.runway import calculate_runway

from backend.app.utils import clean_unicode_minus

@tool
def calculate_fundraising_readiness(summary: FinancialSummary) -> FundraisingResult:
    """
    Analyzes historical startup financials to calculate investor readiness metrics
    and generates a score out of 100 based on standard seed/series-A benchmarks.
    """
    today = date.today()
    sorted_financials = sorted(summary.monthly_financials, key=lambda x: x.month_start)
    financials = [
        m for m in sorted_financials
        if not (m.month_start.year == today.year and m.month_start.month == today.month)
    ]
    if not financials:
        return clean_unicode_minus(FundraisingResult(
            readiness_score=0, 
            metrics=FundraisingMetrics(mrr=None, mrr_growth_rate=None, arr=None, burn_multiple=None, runway_months=Decimal("0"), gross_margin=None), 
            gaps=["No financial history found."]
        ))

    # Exclude leading zero-revenue months for active window
    first_rev_idx = None
    for idx, m in enumerate(financials):
        if m.total_revenue > 0:
            first_rev_idx = idx
            break
            
    if first_rev_idx is not None:
        active_months = financials[first_rev_idx:]
    else:
        active_months = financials

    if not active_months:
        return clean_unicode_minus(FundraisingResult(
            readiness_score=0, 
            metrics=FundraisingMetrics(mrr=None, mrr_growth_rate=None, arr=None, burn_multiple=None, runway_months=Decimal("0"), gross_margin=None), 
            gaps=["No financial history found."]
        ))

    recent = active_months[-1]
    prev = active_months[-2] if len(active_months) > 1 else None
    
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
    # We now reuse the correct burn_multiple calculated over the full active period from calculate_burn_rate.
    burn_multiple = burn_result.burn_multiple

    # Calculate real gross margin over the most recent 3 full months
    recent_3 = active_months[-3:]
    total_rev_3m = sum(m.total_revenue for m in recent_3)
    
    total_cogs_3m = Decimal("0")
    for m in recent_3:
        cogs_val = getattr(m, "total_cogs", Decimal("0"))
        if cogs_val == Decimal("0") and m.category_expenses:
            # Fallback to category_expenses
            for cat, amt in m.category_expenses.items():
                cat_lower = cat.lower()
                if "cogs" in cat_lower or "cost of goods sold" in cat_lower or "cost of sales" in cat_lower:
                    cogs_val += amt
        total_cogs_3m += cogs_val
        
    if total_rev_3m > 0:
        gross_margin = ((total_rev_3m - total_cogs_3m) / total_rev_3m) * Decimal("100")
        gross_margin = gross_margin.quantize(Decimal("0.01"))
    else:
        gross_margin = None
        
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
        
    # Evaluate Gross Margin threshold checks
    if gross_margin is not None:
        if gross_margin >= Decimal("60"):
            score += 0  # optional bump
        else:
            gaps.append(f"Gross margin is '{gross_margin}%'. Seed investors target > 60% for venture-scale software startups.")

    # Baseline existence of revenue
    if mrr > Decimal("0"):
        score += 15
        if mrr_growth_rate and mrr_growth_rate > Decimal("0"):
            score += 15 # Double reward for positive scaling
    else:
        gaps.append("Pre-revenue startups face harder hurdles; focus firmly on product-market validation and runway conservation.")

    return clean_unicode_minus(FundraisingResult(
        readiness_score=score,
        metrics=FundraisingMetrics(
            mrr=mrr,
            mrr_growth_rate=mrr_growth_rate,
            arr=arr,
            burn_multiple=burn_multiple,
            runway_months=runway_months,
            gross_margin=gross_margin
        ),
        gaps=gaps
    ))
