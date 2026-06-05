from decimal import Decimal
from datetime import date
from backend.app.tools.schemas import FinancialSummary, MonthlyFinancial

def _find_group_value(rows: list, group: str) -> Decimal:
    """QBO row listesinden group adına göre Summary değeri çıkarır."""
    for row in rows:
        if row.get("group") == group:
            try:
                return Decimal(str(row["Summary"]["ColData"][1]["value"]))
            except Exception:
                return Decimal("0")
    return Decimal("0")

def _find_bank_total(rows: list) -> Decimal:
    """Balance Sheet'ten Bank Accounts toplamını çıkarır."""
    for row in rows:
        if row.get("group") == "TotalAssets":
            inner_rows = row.get("Rows", {}).get("Row", [])
            for section in inner_rows:
                if section.get("group") == "CurrentAssets":
                    current_rows = section.get("Rows", {}).get("Row", [])
                    for cur in current_rows:
                        if cur.get("group") == "BankAccounts":
                            try:
                                return Decimal(str(cur["Summary"]["ColData"][1]["value"]))
                            except Exception:
                                return Decimal("0")
    return Decimal("0")

def parse_financial_summary(pl_data: dict, bs_data: dict, period_end: date) -> FinancialSummary:
    pl_rows = pl_data.get("Rows", {}).get("Row", [])
    bs_rows = bs_data.get("Rows", {}).get("Row", [])

    total_revenue = _find_group_value(pl_rows, "Income")
    total_expenses = _find_group_value(pl_rows, "Expenses") + _find_group_value(pl_rows, "COGS")
    net_income = _find_group_value(pl_rows, "NetIncome")
    current_cash = _find_bank_total(bs_rows)

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