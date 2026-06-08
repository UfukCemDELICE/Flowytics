import polars as pl
from decimal import Decimal
from datetime import datetime
from langchain_core.tools import tool
from backend.app.tools.schemas import FinancialSummary, MonthlyFinancial

@tool
def parse_qbo_to_financial_summary(pl_data: dict, bs_data: dict) -> FinancialSummary:
    """
    Parses QBO Profit & Loss and Balance Sheet JSON snapshots using Polars 
    to generate a unified FinancialSummary Pydantic model.
    """
    # 1. Keep the existing "monthly_data" fallback logic for test compatibility
    if "monthly_data" in pl_data and pl_data["monthly_data"]:
        try:
            df = pl.DataFrame(pl_data["monthly_data"])
        except Exception:
            # Malformed data: fall through to empty summary
            return FinancialSummary(current_cash_balance=Decimal("0"), monthly_financials=[])
        
        financials = []
        for row in df.iter_rows(named=True):
            try:
                revenue = Decimal(str(row.get("revenue", "0") or "0"))
                expenses = Decimal(str(row.get("expenses", "0") or "0"))
                net_income = Decimal(str(row.get("net_income", "0") or "0"))
                cogs = Decimal(str(row.get("cogs", "0") or "0"))
                month_str = row.get("month", "")
                if not month_str:
                    continue
                financials.append(MonthlyFinancial(
                    month_start=datetime.strptime(month_str, "%Y-%m").date(),
                    total_revenue=revenue,
                    total_expenses=expenses,
                    net_income=net_income,
                    total_cogs=cogs,
                    category_expenses={"COGS": cogs}
                ))
            except (ValueError, TypeError, KeyError):
                # Skip malformed rows rather than crashing the entire parse
                continue
            
        current_cash = Decimal(str(bs_data.get("current_cash_balance", "0") or "0"))
        
        return FinancialSummary(
            current_cash_balance=current_cash,
            monthly_financials=financials
        )

    # 2. Real QBO parser implementation
    pl_rows = pl_data.get("Rows", {}).get("Row", [])
    
    # helper to recursively find a row by group name
    def _find_row_by_group(rows_list, group_name):
        for r in rows_list:
            if r.get("group") == group_name:
                return r
            sub_rows = r.get("Rows", {}).get("Row", [])
            if sub_rows:
                found = _find_row_by_group(sub_rows, group_name)
                if found:
                    return found
        return None

    # helper to recursively collect leaf accounts under a section
    def _collect_leaf_accounts(row: dict, col_idx: int, accounts_dict: dict):
        if not row:
            return
        sub_rows = row.get("Rows", {}).get("Row", [])
        if sub_rows:
            for r in sub_rows:
                _collect_leaf_accounts(r, col_idx, accounts_dict)
        
        col_data = row.get("ColData", [])
        if col_data:
            name = col_data[0].get("value")
            if name and not name.startswith("Total "):
                if col_idx < len(col_data):
                    val = col_data[col_idx].get("value")
                    if val is not None:
                        val_str = str(val).replace("−", "-").replace(",", "").strip()
                        if val_str and val_str != "-":
                            try:
                                accounts_dict[name] = accounts_dict.get(name, Decimal("0")) + Decimal(val_str)
                            except Exception:
                                pass

    # helper to get decimal value from row's ColData at index
    def _get_val_at_idx(row, col_idx) -> Decimal:
        if not row:
            return Decimal("0")
        col_data = row.get("Summary", {}).get("ColData", []) or row.get("ColData", [])
        if col_idx < len(col_data):
            val = col_data[col_idx].get("value")
            if val is not None:
                val_str = str(val).replace("−", "-").replace(",", "").strip()
                if val_str == "" or val_str == "-":
                    return Decimal("0")
                try:
                    return Decimal(val_str)
                except Exception:
                    return Decimal("0")
        return Decimal("0")

    # Columns extraction
    columns = pl_data.get("Columns", {}).get("Column", [])
    money_cols = []
    
    for idx, col in enumerate(columns):
        col_type = col.get("ColType") or col.get("colType") or ""
        if col_type.lower() == "money":
            col_title = col.get("ColTitle") or col.get("colTitle") or ""
            if col_title.lower() in ("total", "account", "row", "collapse"):
                continue
            
            # Parse ColTitle e.g. "Sep 2025" using "%b %Y" format.
            # Skip partial months like "Jun 7-30, 2024" or "Jun 1-7, 2026"
            try:
                dt = datetime.strptime(col_title.strip(), "%b %Y")
                money_cols.append((idx, dt.date()))
            except ValueError:
                continue

    if not money_cols:
        return FinancialSummary(current_cash_balance=Decimal("0"), monthly_financials=[])

    # Rows extraction for Income, Expenses, NetIncome, COGS, OtherExpenses
    income_row = _find_row_by_group(pl_rows, "Income")
    expenses_row = _find_row_by_group(pl_rows, "Expenses")
    net_income_row = _find_row_by_group(pl_rows, "NetIncome")
    cogs_row = _find_row_by_group(pl_rows, "COGS")
    other_expenses_row = _find_row_by_group(pl_rows, "OtherExpenses")

    monthly_financials = []
    for col_idx, month_date in money_cols:
        revenue = _get_val_at_idx(income_row, col_idx)
        cogs = _get_val_at_idx(cogs_row, col_idx)
        opex = _get_val_at_idx(expenses_row, col_idx)
        other_expenses = _get_val_at_idx(other_expenses_row, col_idx)
        total_expenses = opex + cogs + other_expenses
        net_income = _get_val_at_idx(net_income_row, col_idx)
        
        # Extract individual account values from Expenses and COGS sections
        category_expenses = {}
        if expenses_row:
            _collect_leaf_accounts(expenses_row, col_idx, category_expenses)
        if cogs_row:
            _collect_leaf_accounts(cogs_row, col_idx, category_expenses)
        
        # Fallback to COGS total if no individual accounts were found
        if not category_expenses and cogs != 0:
            category_expenses["COGS"] = cogs
            
        monthly_financials.append(MonthlyFinancial(
            month_start=month_date,
            total_revenue=revenue,
            total_expenses=total_expenses,
            net_income=net_income,
            total_cogs=cogs,
            category_expenses=category_expenses
        ))

    monthly_financials.sort(key=lambda x: x.month_start)

    # Balance Sheet extraction for current_cash_balance
    bs_columns = bs_data.get("Columns", {}).get("Column", [])
    bs_target_col_idx = None
    
    # Try to align the latest month column in BS columns
    latest_month_date = max(money_cols, key=lambda x: x[1])[1]
    latest_month_str = latest_month_date.strftime("%b %Y").lower()
    for idx, col in enumerate(bs_columns):
        title = (col.get("ColTitle") or col.get("colTitle") or "").lower()
        if latest_month_str in title or title == latest_month_str:
            bs_target_col_idx = idx
            break

    if bs_target_col_idx is None:
        # Fallback to the same index as the latest money column
        bs_target_col_idx = max(money_cols, key=lambda x: x[1])[0]

    bs_rows = bs_data.get("Rows", {}).get("Row", [])
    assets_row = _find_row_by_group(bs_rows, "Assets") or _find_row_by_group(bs_rows, "TotalAssets")
    
    current_cash = Decimal("0")
    if assets_row:
        current_assets_row = _find_row_by_group(assets_row.get("Rows", {}).get("Row", []), "CurrentAssets")
        if current_assets_row:
            current_cash = _get_val_at_idx(current_assets_row, bs_target_col_idx)
            if current_cash == Decimal("0"):
                bank_row = _find_row_by_group(current_assets_row.get("Rows", {}).get("Row", []), "BankAccounts")
                if bank_row:
                    current_cash = _get_val_at_idx(bank_row, bs_target_col_idx)
    else:
        # Fallback to searching currentassets anywhere
        current_assets_row = _find_row_by_group(bs_rows, "CurrentAssets")
        if current_assets_row:
            current_cash = _get_val_at_idx(current_assets_row, bs_target_col_idx)
            if current_cash == Decimal("0"):
                bank_row = _find_row_by_group(current_assets_row.get("Rows", {}).get("Row", []), "BankAccounts")
                if bank_row:
                    current_cash = _get_val_at_idx(bank_row, bs_target_col_idx)

    return FinancialSummary(
        current_cash_balance=current_cash,
        monthly_financials=monthly_financials
    )
