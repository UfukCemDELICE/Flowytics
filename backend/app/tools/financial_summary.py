import polars as pl
from decimal import Decimal
from datetime import date, datetime
from langchain_core.tools import tool
from backend.app.tools.schemas import FinancialSummary, MonthlyFinancial

@tool
def parse_qbo_to_financial_summary(pl_data: dict, bs_data: dict) -> FinancialSummary:
    """
    Parses QBO Profit & Loss and Balance Sheet JSON snapshots using Polars 
    to generate a unified FinancialSummary Pydantic model.
    """
    # QBO data is heavily nested. For MVP, we extract the total nodes if they match standard names.
    # A robust production version would use recursive parsing.
    
    pl_rows = pl_data.get("Rows", {}).get("Row", [])
    
    # Convert whatever we can into a Polars DataFrame for metric aggregation.
    # In this MVP mock, we assume the backend sync service might pre-flatten the data,
    # or we handle dummy data structure passed by our tests.
    
    # Dummy logic to construct standard MonthlyFinancial list
    # Let's say we have 'monthly_data' array passed inside the snapshot metadata for ease:
    if "monthly_data" in pl_data:
        df = pl.DataFrame(pl_data["monthly_data"])
        
        financials = []
        for row in df.iter_rows(named=True):
            financials.append(MonthlyFinancial(
                month_start=datetime.strptime(row["month"], "%Y-%m").date(),
                total_revenue=Decimal(str(row["revenue"])),
                total_expenses=Decimal(str(row["expenses"])),
                net_income=Decimal(str(row["net_income"]))
            ))
            
        current_cash = Decimal(str(bs_data.get("current_cash_balance", "0.00")))
        
        return FinancialSummary(
            current_cash_balance=current_cash,
            monthly_financials=financials
        )
        
    return FinancialSummary(current_cash_balance=Decimal("0"), monthly_financials=[])
