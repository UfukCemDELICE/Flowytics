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

def _get_meta_value(metadata_list, key: str):
    if isinstance(metadata_list, list):
        for item in metadata_list:
            if item.get("Name") == key or item.get("Name") == key.lower() or item.get("Name") == (key[0].lower() + key[1:]):
                return item.get("Value")
            if item.get("name") == key or item.get("name") == key.lower() or item.get("name") == (key[0].lower() + key[1:]):
                return item.get("value")
    elif isinstance(metadata_list, dict):
        return (metadata_list.get(key) or 
                metadata_list.get(key.lower()) or 
                metadata_list.get(key[0].lower() + key[1:]))
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
                col_data = row.get("Summary", {}).get("ColData", []) or row.get("ColData", [])
                first_col = col_data[0].get("value", "")
                if first_col in allowed_labels:
                    match = True
            except Exception:
                pass
                
        if match:
            try:
                col_data = row.get("Summary", {}).get("ColData", []) or row.get("ColData", [])
                if col_idx < len(col_data):
                    val = col_data[col_idx].get("value")
                    if val is not None:
                        val_str = str(val).replace(",", "").strip()
                        return Decimal(val_str) if val_str else Decimal("0")
                    return Decimal("0")
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
                col_data = row.get("Summary", {}).get("ColData", []) or row.get("ColData", [])
                first_col = col_data[0].get("value", "")
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
                        col_data = section.get("Summary", {}).get("ColData", []) or section.get("ColData", [])
                        first_col = col_data[0].get("value", "")
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
                                col_data = cur.get("Summary", {}).get("ColData", []) or cur.get("ColData", [])
                                first_col = col_data[0].get("value", "")
                                if first_col in ["Total Bank Accounts", "Bank Accounts", "BankAccounts", "Total BankAccounts"]:
                                    match_bank = True
                            except Exception:
                                pass
                                
                        if match_bank:
                            try:
                                col_data = cur.get("Summary", {}).get("ColData", []) or cur.get("ColData", [])
                                if col_idx < len(col_data):
                                    val = col_data[col_idx].get("value")
                                    if val is not None:
                                        val_str = str(val).replace(",", "").strip()
                                        return Decimal(val_str) if val_str else Decimal("0")
                                    return Decimal("0")
                            except Exception:
                                return Decimal("0")
    # Fallback to checking any row if the nested structure is flatter (e.g. mock data)
    for row in rows:
        try:
            col_data = row.get("Summary", {}).get("ColData", []) or row.get("ColData", [])
            first_col = col_data[0].get("value", "")
            if first_col in ["Total Bank Accounts", "Bank Accounts", "BankAccounts", "Total BankAccounts", "Total Assets"]:
                if col_idx < len(col_data):
                    val = col_data[col_idx].get("value")
                    if val is not None:
                        val_str = str(val).replace(",", "").strip()
                        return Decimal(val_str) if val_str else Decimal("0")
                    return Decimal("0")
        except Exception:
            pass
            
    return Decimal("0")

def parse_financial_summary(pl_data: dict, bs_data: dict, period_end: date) -> FinancialSummary:
    columns = pl_data.get("Columns", {}).get("Column", [])
    month_cols = []
    
    for i, col in enumerate(columns):
        col_type = col.get("ColType") or col.get("colType") or ""
        if col_type.lower() == "account":
            continue
            
        title = col.get("ColTitle") or col.get("colTitle") or ""
        if title.lower() in ("total", "collapse", "row"):
            continue
            
        # Try metadata StartDate
        metadata = col.get("MetaData") or col.get("metadata") or {}
        start_date_str = _get_meta_value(metadata, "StartDate")
        
        d = None
        if start_date_str:
            try:
                if isinstance(start_date_str, date):
                    d = start_date_str
                elif isinstance(start_date_str, datetime):
                    d = start_date_str.date()
                else:
                    d = datetime.strptime(str(start_date_str).strip(), "%Y-%m-%d").date()
            except ValueError:
                pass
                
        if not d and title:
            d = parse_qbo_column_date(str(title))
            
        if d:
            month_cols.append((i, d))
            
    pl_rows = pl_data.get("Rows", {}).get("Row", [])
    bs_rows = bs_data.get("Rows", {}).get("Row", [])

    if not month_cols:
        # Fallback to existing single-month behavior
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

        monthly_financials = []
        if not (monthly.total_revenue == 0 and monthly.total_expenses == 0 and monthly.net_income == 0):
            monthly_financials.append(monthly)

        return FinancialSummary(
            current_cash_balance=current_cash,
            monthly_financials=monthly_financials,
        )
        
    monthly_financials = []
    
    for col_idx, month_date in month_cols:
        total_revenue = _find_group_value_for_col(pl_rows, "Income", col_idx) + _find_group_value_for_col(pl_rows, "OtherIncome", col_idx)
        total_expenses = _find_group_value_for_col(pl_rows, "Expenses", col_idx) + _find_group_value_for_col(pl_rows, "COGS", col_idx) + _find_group_value_for_col(pl_rows, "OtherExpenses", col_idx)
        net_income = _find_group_value_for_col(pl_rows, "NetIncome", col_idx)
        
        # Skip months where total_revenue, total_expenses, and net_income are all 0/empty
        if total_revenue == 0 and total_expenses == 0 and net_income == 0:
            continue
            
        monthly_financials.append(
            MonthlyFinancial(
                month_start=month_date,
                total_revenue=total_revenue,
                total_expenses=total_expenses,
                net_income=net_income,
            )
        )
        
    # Sort monthly_financials by month_start
    monthly_financials.sort(key=lambda x: x.month_start)
    
    # Get cash balance of the latest month column
    if month_cols:
        sorted_month_cols = sorted(month_cols, key=lambda x: x[1])
        last_col_idx = sorted_month_cols[-1][0]
        current_cash = _find_bank_total_for_col(bs_rows, last_col_idx)
    else:
        current_cash = Decimal("0")
        
    return FinancialSummary(
        current_cash_balance=current_cash,
        monthly_financials=monthly_financials,
    )