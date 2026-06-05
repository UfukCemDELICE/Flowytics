from decimal import Decimal
from datetime import date, datetime
import re
from backend.app.tools.schemas import FinancialSummary, MonthlyFinancial

def parse_qbo_column_date(col_title: str) -> date | None:
    """Robustly converts QBO month column headers into date objects."""
    title = col_title.strip()
    if not title or title.lower() in ("total", "account", "row", "collapse"):
        return None
    
    # Try YYYY-MM-DD
    try:
        return datetime.strptime(title, "%Y-%m-%d").date()
    except ValueError:
        pass
    
    # Try YYYY-MM
    try:
        return datetime.strptime(title, "%Y-%m").date()
    except ValueError:
        pass
    
    # Try MMM YYYY (e.g. Jan 2026, Jun 2026)
    try:
        return datetime.strptime(title, "%b %Y").date()
    except ValueError:
        pass
        
    # Try MMMM YYYY (e.g. June 2026)
    try:
        return datetime.strptime(title, "%B %Y").date()
    except ValueError:
        pass

    # Try MM/YYYY
    try:
        return datetime.strptime(title, "%m/%Y").date()
    except ValueError:
        pass

    # Try MM/DD/YYYY
    try:
        return datetime.strptime(title, "%m/%d/%Y").date()
    except ValueError:
        pass
        
    return None

def _find_group_value_for_col(rows: list, group: str, col_idx: int) -> Decimal:
    """QBO row listesinden group adına veya label'a göre belirli kolondaki Summary değerini çıkarır."""
    group_labels = {
        "Income": ["Income", "Total Income", "Gross Profit"],
        "OtherIncome": ["OtherIncome", "Other Income", "Total Other Income"],
        "Expenses": ["Expenses", "Total Expenses", "Total Expense"],
        "COGS": ["COGS", "Cost of Goods Sold", "Total Cost of Goods Sold"],
        "OtherExpenses": ["OtherExpenses", "Other Expenses", "Total Other Expenses"],
        "NetIncome": ["NetIncome", "Net Income", "Net Profit"]
    }
    allowed_labels = group_labels.get(group, [group])
    
    for row in rows:
        match = False
        if row.get("group") == group:
            match = True
        else:
            # Check the first ColData element's value (usually the account/group name)
            try:
                first_col = row["Summary"]["ColData"][0].get("value", "")
                if first_col in allowed_labels:
                    match = True
            except Exception:
                pass
                
        if match:
            try:
                col_data = row["Summary"]["ColData"]
                if col_idx < len(col_data):
                    val = col_data[col_idx].get("value")
                    return Decimal(str(val)) if val is not None else Decimal("0")
            except Exception:
                return Decimal("0")
    return Decimal("0")

def _find_bank_total_for_col(rows: list, col_idx: int) -> Decimal:
    """Balance Sheet'ten Bank Accounts toplamını belirli bir kolon indexine göre çıkarır."""
    for row in rows:
        match_assets = False
        if row.get("group") == "TotalAssets":
            match_assets = True
        else:
            try:
                first_col = row["Summary"]["ColData"][0].get("value", "")
                if first_col in ["Total Assets", "TotalAssets"]:
                    match_assets = True
            except Exception:
                pass
                
        if match_assets:
            inner_rows = row.get("Rows", {}).get("Row", [])
            for section in inner_rows:
                match_curr = False
                if section.get("group") == "CurrentAssets":
                    match_curr = True
                else:
                    try:
                        first_col = section["Summary"]["ColData"][0].get("value", "")
                        if first_col in ["Total Current Assets", "CurrentAssets", "Total CurrentAssets"]:
                            match_curr = True
                    except Exception:
                        pass
                        
                if match_curr:
                    current_rows = section.get("Rows", {}).get("Row", [])
                    for cur in current_rows:
                        match_bank = False
                        if cur.get("group") == "BankAccounts":
                            match_bank = True
                        else:
                            try:
                                first_col = cur["Summary"]["ColData"][0].get("value", "")
                                if first_col in ["Total Bank Accounts", "Bank Accounts", "BankAccounts", "Total BankAccounts"]:
                                    match_bank = True
                            except Exception:
                                pass
                                
                        if match_bank:
                            try:
                                col_data = cur["Summary"]["ColData"]
                                if col_idx < len(col_data):
                                    val = col_data[col_idx].get("value")
                                    return Decimal(str(val)) if val is not None else Decimal("0")
                            except Exception:
                                return Decimal("0")
    # Fallback to checking any row if the nested structure is flatter (e.g. mock data)
    for row in rows:
        try:
            first_col = row["Summary"]["ColData"][0].get("value", "")
            if first_col in ["Total Bank Accounts", "Bank Accounts", "BankAccounts", "Total BankAccounts", "Total Assets"]:
                col_data = row["Summary"]["ColData"]
                if col_idx < len(col_data):
                    val = col_data[col_idx].get("value")
                    return Decimal(str(val)) if val is not None else Decimal("0")
        except Exception:
            pass
            
    return Decimal("0")

def parse_financial_summary(pl_data: dict, bs_data: dict, period_end: date) -> FinancialSummary:
    columns = pl_data.get("Columns", {}).get("Column", [])
    month_cols = []
    
    for i, col in enumerate(columns):
        title = col.get("colTitle", "")
        if not title or title.lower() in ("total", "account", "row", "collapse"):
            continue
        d = parse_qbo_column_date(title)
        if d:
            month_cols.append((i, d))
            
    if not month_cols:
        # Fallback to existing single-month behavior
        pl_rows = pl_data.get("Rows", {}).get("Row", [])
        bs_rows = bs_data.get("Rows", {}).get("Row", [])

        total_revenue = _find_group_value_for_col(pl_rows, "Income", 1) + _find_group_value_for_col(pl_rows, "OtherIncome", 1)
        total_expenses = _find_group_value_for_col(pl_rows, "Expenses", 1) + _find_group_value_for_col(pl_rows, "COGS", 1) + _find_group_value_for_col(pl_rows, "OtherExpenses", 1)
        net_income = _find_group_value_for_col(pl_rows, "NetIncome", 1)
        current_cash = _find_bank_total_for_col(bs_rows, 1)

        monthly = MonthlyFinancial(
            month_start=date(period_end.year, period_end.month, 1),
            total_revenue=total_revenue,
            total_expenses=total_expenses,
            net_income=net_income,
        )

        return FinancialSummary(
            current_cash_balance=current_cash,
            monthly_financials=[monthly],
        )
        
    monthly_financials = []
    pl_rows = pl_data.get("Rows", {}).get("Row", [])
    bs_rows = bs_data.get("Rows", {}).get("Row", [])
    
    # Sort columns by date
    month_cols.sort(key=lambda x: x[1])
    
    for col_idx, month_date in month_cols:
        total_revenue = _find_group_value_for_col(pl_rows, "Income", col_idx) + _find_group_value_for_col(pl_rows, "OtherIncome", col_idx)
        total_expenses = _find_group_value_for_col(pl_rows, "Expenses", col_idx) + _find_group_value_for_col(pl_rows, "COGS", col_idx) + _find_group_value_for_col(pl_rows, "OtherExpenses", col_idx)
        net_income = _find_group_value_for_col(pl_rows, "NetIncome", col_idx)
        
        monthly_financials.append(
            MonthlyFinancial(
                month_start=date(month_date.year, month_date.month, 1),
                total_revenue=total_revenue,
                total_expenses=total_expenses,
                net_income=net_income,
            )
        )
        
    # Get cash balance of the latest month column
    last_col_idx = month_cols[-1][0]
    current_cash = _find_bank_total_for_col(bs_rows, last_col_idx)
    
    return FinancialSummary(
        current_cash_balance=current_cash,
        monthly_financials=monthly_financials,
    )