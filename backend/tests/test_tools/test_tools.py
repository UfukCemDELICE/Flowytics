from decimal import Decimal
from backend.app.tools.burn_rate import calculate_burn_rate
from backend.app.tools.runway import calculate_runway
from backend.app.tools.cash_forecast import calculate_cash_forecast

def test_burn_rate_healthy(profile_healthy):
    result = calculate_burn_rate(profile_healthy)
    
    # Expect stable or decreasing burn because net income is -10K, -9K, -7K (getting better)
    # So net_burn is 10K, 9K, 7K. This is a decreasing trend.
    assert result.trend in ["decreasing", "stable"]
    assert result.net_burn_monthly > Decimal("0")
    assert result.period_months == 6

def test_burn_rate_dying(profile_dying):
    result = calculate_burn_rate(profile_dying)
    
    # Net income is -45K, -50.5K, -56K -> net burn is 45K, 50.5K, 56K. Increasing trend.
    assert result.trend == "increasing"
    assert result.net_burn_monthly > Decimal("45000")
    assert result.period_months == 3

def test_runway_healthy(profile_healthy):
    burn = calculate_burn_rate(profile_healthy)
    runway = calculate_runway(profile_healthy, burn)
    
    # Healthy profile has 500K cash and ~5K burn. Runway should be huge.
    assert runway.runway_status == "healthy"
    assert runway.runway_months > Decimal("12")

def test_runway_dying(profile_dying):
    burn = calculate_burn_rate(profile_dying)
    runway = calculate_runway(profile_dying, burn)
    
    # Dying profile has 40K cash and ~50K average burn.
    # Runway should be < 1 month -> critical
    assert runway.runway_status == "critical"
    assert runway.runway_months < Decimal("3")

def test_runway_profitable(profile_profitable):
    burn = calculate_burn_rate(profile_profitable)
    runway = calculate_runway(profile_profitable, burn)
    
    # Net income is positive -> burn is negative or zero. Runway should be healthy/infinite (9999).
    assert runway.runway_status == "healthy"
    assert runway.runway_months == Decimal("9999")
    
def test_cash_forecast(profile_healthy):
    forecast = calculate_cash_forecast(profile_healthy)
    
    assert len(forecast.weeks) == 13
    assert forecast.weeks[0].projected_inflow > Decimal("0")
    # For healthy, zero cash should not happen in 13 weeks
    assert forecast.zero_cash_week is None

def test_cash_forecast_dying(profile_dying):
    forecast = calculate_cash_forecast(profile_dying)
    
    # Dying profile runs out of money almost immediately. 
    # Current cash: 40k. Avg outflow: 55k/mo -> 12.7k/wk. 
    # Avg inflow: 4.5k/mo -> 1k/wk. Net weekly: -11.7k. 40k / 11.7k = week 4.
    assert forecast.zero_cash_week is not None
    assert forecast.zero_cash_week <= 5
