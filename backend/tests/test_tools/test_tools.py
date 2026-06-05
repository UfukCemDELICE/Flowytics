from decimal import Decimal
from backend.app.tools.burn_rate import calculate_burn_rate
from backend.app.tools.runway import calculate_runway
from backend.app.tools.cash_forecast import calculate_cash_forecast

def test_burn_rate_healthy(profile_healthy):
    result = calculate_burn_rate.invoke({"summary": profile_healthy})
    assert result.trend in ["decreasing", "stable"]
    assert result.net_burn_monthly > Decimal("0")
    assert result.period_months == 6

def test_burn_rate_dying(profile_dying):
    result = calculate_burn_rate.invoke({"summary": profile_dying})
    assert result.trend == "increasing"
    assert result.net_burn_monthly > Decimal("45000")
    assert result.period_months == 3

def test_runway_healthy(profile_healthy):
    burn = calculate_burn_rate.invoke({"summary": profile_healthy})
    runway = calculate_runway.invoke({"summary": profile_healthy, "burn_rate": burn})
    assert runway.runway_status == "healthy"
    assert runway.runway_months > Decimal("12")

def test_runway_dying(profile_dying):
    burn = calculate_burn_rate.invoke({"summary": profile_dying})
    runway = calculate_runway.invoke({"summary": profile_dying, "burn_rate": burn})
    assert runway.runway_status == "critical"
    assert runway.runway_months < Decimal("3")

def test_runway_profitable(profile_profitable):
    burn = calculate_burn_rate.invoke({"summary": profile_profitable})
    runway = calculate_runway.invoke({"summary": profile_profitable, "burn_rate": burn})
    assert runway.runway_status == "healthy"
    assert runway.runway_months == Decimal("9999")
    
def test_cash_forecast(profile_healthy):
    forecast = calculate_cash_forecast.invoke({"summary": profile_healthy})
    assert len(forecast.weeks) == 13
    assert forecast.weeks[0].projected_inflow > Decimal("0")
    assert forecast.zero_cash_week is None

def test_cash_forecast_dying(profile_dying):
    forecast = calculate_cash_forecast.invoke({"summary": profile_dying})
    assert forecast.zero_cash_week is not None
    assert forecast.zero_cash_week <= 5

def test_qbo_parser_sandbox_values():
    from datetime import date
    from backend.app.tools.qbo_parser import parse_financial_summary

    pl_data = {
        "Rows": {
            "Row": [
                {
                    "group": "Income",
                    "Summary": {"ColData": [{}, {"value": "10200.77"}]}
                },
                {
                    "group": "Expenses",
                    "Summary": {"ColData": [{}, {"value": "5642.31"}]}
                },
                {
                    "group": "OtherExpenses",
                    "Summary": {"ColData": [{}, {"value": "2916.00"}]}
                },
                {
                    "group": "NetIncome",
                    "Summary": {"ColData": [{}, {"value": "1642.46"}]}
                }
            ]
        }
    }
    bs_data = {"Rows": {"Row": []}}
    
    summary = parse_financial_summary(pl_data, bs_data, date(2026, 6, 5))
    monthly = summary.monthly_financials[0]
    
    assert monthly.total_revenue == Decimal("10200.77")
    assert monthly.total_expenses == Decimal("8558.31")
    assert monthly.net_income == Decimal("1642.46")
    assert monthly.total_revenue - monthly.total_expenses == monthly.net_income

def test_qbo_parser_multi_month_values():
    from datetime import date
    from backend.app.tools.qbo_parser import parse_financial_summary

    pl_data = {
        "Columns": {
            "Column": [
                {"colTitle": "", "colType": "Account"},
                {"colTitle": "Jan 2026", "colType": "String"},
                {"colTitle": "Feb 2026", "colType": "String"},
                {"colTitle": "Mar 2026", "colType": "String"},
                {"colTitle": "Total", "colType": "String"}
            ]
        },
        "Rows": {
            "Row": [
                {
                    "group": "Income",
                    "Summary": {"ColData": [{"value": "Total Income"}, {"value": "1000.00"}, {"value": "2000.00"}, {"value": "3000.00"}, {"value": "6000.00"}]}
                },
                {
                    "group": "Expenses",
                    "Summary": {"ColData": [{"value": "Total Expenses"}, {"value": "600.00"}, {"value": "1200.00"}, {"value": "1800.00"}, {"value": "3600.00"}]}
                },
                {
                    "group": "NetIncome",
                    "Summary": {"ColData": [{"value": "Net Income"}, {"value": "400.00"}, {"value": "800.00"}, {"value": "1200.00"}, {"value": "2400.00"}]}
                }
            ]
        }
    }
    bs_data = {
        "Columns": {
            "Column": [
                {"colTitle": "", "colType": "Account"},
                {"colTitle": "Jan 2026", "colType": "String"},
                {"colTitle": "Feb 2026", "colType": "String"},
                {"colTitle": "Mar 2026", "colType": "String"},
                {"colTitle": "Total", "colType": "String"}
            ]
        },
        "Rows": {
            "Row": [
                {
                    "group": "TotalAssets",
                    "Rows": {
                        "Row": [
                            {
                                "group": "CurrentAssets",
                                "Rows": {
                                    "Row": [
                                        {
                                            "group": "BankAccounts",
                                            "Summary": {"ColData": [{"value": "Total Bank Accounts"}, {"value": "10000.00"}, {"value": "11000.00"}, {"value": "12000.00"}, {"value": "12000.00"}]}
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                }
            ]
        }
    }

    summary = parse_financial_summary(pl_data, bs_data, date(2026, 6, 5))
    assert len(summary.monthly_financials) == 3
    
    # Check Jan 2026
    jan = summary.monthly_financials[0]
    assert jan.month_start == date(2026, 1, 1)
    assert jan.total_revenue == Decimal("1000.00")
    assert jan.total_expenses == Decimal("600.00")
    assert jan.net_income == Decimal("400.00")

    # Check Feb 2026
    feb = summary.monthly_financials[1]
    assert feb.month_start == date(2026, 2, 1)
    assert feb.total_revenue == Decimal("2000.00")
    assert feb.total_expenses == Decimal("1200.00")
    assert feb.net_income == Decimal("800.00")

    # Check Mar 2026
    mar = summary.monthly_financials[2]
    assert mar.month_start == date(2026, 3, 1)
    assert mar.total_revenue == Decimal("3000.00")
    assert mar.total_expenses == Decimal("1800.00")
    assert mar.net_income == Decimal("1200.00")

    # Check current cash balance
    assert summary.current_cash_balance == Decimal("12000.00")

def test_qbo_parser_two_year_period():
    from datetime import date, timedelta, datetime
    from backend.app.tools.qbo_parser import parse_financial_summary
    
    # Generate columns from Jun 2024 to Jun 2026
    start_year, start_month = 2024, 6
    end_year, end_month = 2026, 6
    
    columns_list = [{"colTitle": "", "colType": "Account"}]
    current_year, current_month = start_year, start_month
    
    month_dates = []
    while (current_year, current_month) <= (end_year, end_month):
        d = date(current_year, current_month, 1)
        month_dates.append(d)
        
        # Increment month
        if current_month == 12:
            current_month = 1
            current_year += 1
        else:
            current_month += 1
            
    # Add columns
    for d in month_dates:
        col_title = d.strftime("%b %Y") # e.g. Jun 2024
        start_date_str = d.strftime("%Y-%m-%d")
        # calculate last day of month d
        next_m_year = d.year + (1 if d.month == 12 else 0)
        next_m_month = 1 if d.month == 12 else d.month + 1
        end_date_str = (date(next_m_year, next_m_month, 1) - timedelta(days=1)).strftime("%Y-%m-%d")
        
        columns_list.append({
            "colTitle": col_title,
            "colType": "Money",
            "MetaData": {
                "StartDate": start_date_str,
                "EndDate": end_date_str
            }
        })
        
    # Also add a Total column at the end
    columns_list.append({"colTitle": "Total", "colType": "Money"})
    
    # We have ColData list for each row.
    income_col_data = [{"value": "Total Income"}]
    expenses_col_data = [{"value": "Total Expenses"}]
    cogs_col_data = [{"value": "Total Cost of Goods Sold"}]
    other_inc_col_data = [{"value": "Total Other Income"}]
    other_exp_col_data = [{"value": "Total Other Expenses"}]
    net_inc_col_data = [{"value": "Net Income"}]
    
    bank_col_data = [{"value": "Total Bank Accounts"}]
    
    for idx, d in enumerate(month_dates):
        if idx % 2 == 0:
            # Non-zero month
            income_col_data.append({"value": str(10000 + idx * 100)})
            expenses_col_data.append({"value": str(5000 + idx * 50)})
            cogs_col_data.append({"value": "500"})
            other_inc_col_data.append({"value": "100"})
            other_exp_col_data.append({"value": "50"})
            net_inc_col_data.append({"value": str(10000 + idx * 100 + 100 - (5000 + idx * 50 + 500 + 50))}) # rev - exp
            bank_col_data.append({"value": str(50000 + idx * 1000)})
        else:
            # Zero month
            income_col_data.append({"value": "0"})
            expenses_col_data.append({"value": ""}) # empty string
            cogs_col_data.append({"value": "0"})
            other_inc_col_data.append({"value": "0"})
            other_exp_col_data.append({"value": None}) # None value
            net_inc_col_data.append({"value": "0"})
            bank_col_data.append({"value": "0"})
            
    # Add Total column values
    income_col_data.append({"value": "99999"})
    expenses_col_data.append({"value": "99999"})
    cogs_col_data.append({"value": "99999"})
    other_inc_col_data.append({"value": "99999"})
    other_exp_col_data.append({"value": "99999"})
    net_inc_col_data.append({"value": "99999"})
    bank_col_data.append({"value": "99999"})
    
    pl_data = {
        "Columns": {"Column": columns_list},
        "Rows": {
            "Row": [
                {"group": "Income", "Summary": {"ColData": income_col_data}},
                {"group": "Expenses", "Summary": {"ColData": expenses_col_data}},
                {"group": "COGS", "Summary": {"ColData": cogs_col_data}},
                {"group": "OtherIncome", "Summary": {"ColData": other_inc_col_data}},
                {"group": "OtherExpenses", "Summary": {"ColData": other_exp_col_data}},
                {"group": "NetIncome", "Summary": {"ColData": net_inc_col_data}},
            ]
        }
    }
    
    bs_data = {
        "Columns": {"Column": columns_list},
        "Rows": {
            "Row": [
                {
                    "group": "TotalAssets",
                    "Rows": {
                        "Row": [
                            {
                                "group": "CurrentAssets",
                                "Rows": {
                                    "Row": [
                                        {
                                            "group": "BankAccounts",
                                            "Summary": {"ColData": bank_col_data}
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                }
            ]
        }
    }
    
    # Call the parser
    summary = parse_financial_summary(pl_data, bs_data, date(2026, 6, 30))
    
    # Assertions
    assert len(summary.monthly_financials) >= 10
    # Expected exactly 13 non-zero months
    assert len(summary.monthly_financials) == 13
    
    # Check that they are sorted chronologically
    for i in range(len(summary.monthly_financials) - 1):
        assert summary.monthly_financials[i].month_start < summary.monthly_financials[i+1].month_start
        
    # Check values for the first non-zero month (index 0, Jun 2024)
    first_month = summary.monthly_financials[0]
    assert first_month.month_start == date(2024, 6, 1)
    # total_revenue: Income + OtherIncome = 10000 + 100 = 10100
    assert first_month.total_revenue == Decimal("10100")
    # total_expenses: Expenses + COGS + OtherExpenses = 5000 + 500 + 50 = 5550
    assert first_month.total_expenses == Decimal("5550")
    # net_income: 10100 - 5550 = 4550
    assert first_month.net_income == Decimal("4550")
    
    # Check current cash balance (from the latest month column - Total is excluded because ColTitle is Total, so the last month is Jun 2026 which is idx 25)
    # The last month's column is Jun 2026, which is an even index, so bank accounts has 50000 + 24 * 1000 = 74000
    assert summary.current_cash_balance == Decimal("74000")
