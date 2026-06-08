import logging
import random
from decimal import Decimal
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from backend.app.database import get_session, _get_engine
from backend.app.models.integration import Integration
from backend.app.integrations.quickbooks import get_qbo_client
from backend.app.tools.qbo_parser import parse_financial_summary, parse_qbo_column_date
from backend.app.tools.schemas import FinancialSummary
from backend.app.tools.run_rate import calculate_run_rate

from quickbooks.exceptions import QuickbooksException
from quickbooks.objects.payment import Payment
from quickbooks.objects.billpayment import BillPayment
from quickbooks.objects.refundreceipt import RefundReceipt
from quickbooks.objects.creditmemo import CreditMemo
from quickbooks.objects.vendorcredit import VendorCredit
from quickbooks.objects.invoice import Invoice
from quickbooks.objects.salesreceipt import SalesReceipt
from quickbooks.objects.bill import Bill
from quickbooks.objects.purchase import Purchase
from quickbooks.objects.deposit import Deposit, DepositLine, DepositLineDetail
from quickbooks.objects.transfer import Transfer
from quickbooks.objects.journalentry import JournalEntry
from quickbooks.objects.estimate import Estimate
from quickbooks.objects.purchaseorder import PurchaseOrder
from quickbooks.objects.timeactivity import TimeActivity
from quickbooks.objects.account import Account
from quickbooks.objects.item import Item
from quickbooks.objects.customer import Customer

from quickbooks.objects.detailline import (
    AccountBasedExpenseLine,
    AccountBasedExpenseLineDetail,
    SalesItemLine,
    SalesItemLineDetail,
)

router = APIRouter(prefix="/admin", tags=["admin"])
logger = logging.getLogger(__name__)

# --- Account, Item, and Customer Helpers ---

def find_account_by_name(qb, name: str) -> Account | None:
    escaped_name = name.replace("'", "\\'")
    try:
        results = Account.query(f"SELECT * FROM Account WHERE Name = '{escaped_name}' AND Active IN (true, false)", qb=qb)
        if results:
            return results[0]
    except Exception as e:
        logger.warning(f"Error querying account '{name}': {e}")
    return None

def get_or_create_account(qb, name: str, account_type: str, sub_type: str) -> Account:
    acc = find_account_by_name(qb, name)
    if acc:
        if not acc.Active:
            logger.info(f"Reactivating account '{acc.Name}'...")
            acc.Active = True
            acc.save(qb=qb)
        return acc
    
    # synonym lookup
    if name == "Rent":
        for syn in ["Rent or Lease", "Rent Expense"]:
            acc = find_account_by_name(qb, syn)
            if acc:
                if not acc.Active:
                    logger.info(f"Reactivating account '{acc.Name}'...")
                    acc.Active = True
                    acc.save(qb=qb)
                return acc
    elif name == "Legal & Professional":
        for syn in ["Legal & Professional Fees", "Legal and Professional", "Legal & professional fees"]:
            acc = find_account_by_name(qb, syn)
            if acc:
                if not acc.Active:
                    logger.info(f"Reactivating account '{acc.Name}'...")
                    acc.Active = True
                    acc.save(qb=qb)
                return acc
    elif name == "Advertising":
        for syn in ["Advertising/Promotional", "Advertising Expense"]:
            acc = find_account_by_name(qb, syn)
            if acc:
                if not acc.Active:
                    logger.info(f"Reactivating account '{acc.Name}'...")
                    acc.Active = True
                    acc.save(qb=qb)
                return acc
    elif name == "Checking":
        for syn in ["Checking (Reg)", "Checking Account", "Checking - Operating"]:
            acc = find_account_by_name(qb, syn)
            if acc:
                if not acc.Active:
                    logger.info(f"Reactivating account '{acc.Name}'...")
                    acc.Active = True
                    acc.save(qb=qb)
                return acc
                
    # Create new
    logger.info(f"Creating account '{name}' of type '{account_type}'")
    acc = Account()
    acc.Name = name
    acc.AccountType = account_type
    acc.AccountSubType = sub_type
    acc.Active = True
    try:
        acc.save(qb=qb)
    except Exception as e:
        # Try to refetch in case it succeeded despite exception
        refetched = find_account_by_name(qb, name)
        if refetched:
            return refetched
        
        error_msg = (
            f"FAILED TO CREATE ACCOUNT: Name='{name}', AccountType='{account_type}', "
            f"AccountSubType='{sub_type}'. Error: {str(e)}"
        )
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e
    return acc

def find_item_by_name(qb, name: str) -> Item | None:
    escaped_name = name.replace("'", "\\'")
    try:
        results = Item.query(f"SELECT * FROM Item WHERE Name = '{escaped_name}' AND Active IN (true, false)", qb=qb)
        if results:
            return results[0]
    except Exception as e:
        logger.warning(f"Error querying item '{name}': {e}")
    return None

def get_or_create_item(qb, name: str, income_account: Account) -> Item:
    item = find_item_by_name(qb, name)
    if item:
        if not item.Active:
            logger.info(f"Reactivating item '{name}'...")
            item.Active = True
            item.save(qb=qb)
        return item
        
    logger.info(f"Creating item '{name}' linked to account '{income_account.Name}'")
    item = Item()
    item.Name = name
    item.Type = "Service"
    item.IncomeAccountRef = income_account.to_ref()
    item.Active = True
    try:
        item.save(qb=qb)
    except Exception as e:
        logger.error(f"Failed to save item '{name}': {e}")
        item = find_item_by_name(qb, name)
        if not item:
            raise e
    return item

def find_customer_by_name(qb, name: str) -> Customer | None:
    escaped_name = name.replace("'", "\\'")
    try:
        results = Customer.query(f"SELECT * FROM Customer WHERE DisplayName = '{escaped_name}' AND Active IN (true, false)", qb=qb)
        if results:
            return results[0]
    except Exception as e:
        logger.warning(f"Error querying customer '{name}': {e}")
    return None

def get_or_create_customer(qb, name: str) -> Customer:
    cust = find_customer_by_name(qb, name)
    if cust:
        if not cust.Active:
            logger.info(f"Reactivating customer '{name}'...")
            cust.Active = True
            cust.save(qb=qb)
        return cust
        
    logger.info(f"Creating customer '{name}'")
    cust = Customer()
    cust.DisplayName = name
    cust.Active = True
    try:
        cust.save(qb=qb)
    except Exception as e:
        logger.error(f"Failed to save customer '{name}': {e}")
        cust = find_customer_by_name(qb, name)
        if not cust:
            raise e
    return cust


# --- Background Tasks ---

async def run_qbo_clean_task(tenant_id: str, realm_id: str):
    logger.info(f"[CLEAN] Starting clean background task for tenant {tenant_id}, realm {realm_id}")
    from backend.app.database import _get_engine
    _, session_factory = _get_engine()
    
    async with session_factory() as session:
        try:
            qb = await get_qbo_client(realm_id=realm_id, tenant_id=tenant_id, session=session)
        except Exception as e:
            logger.error(f"[CLEAN] Failed to get QBO client: {e}")
            return
            
        # 1. Delete transactions in dependency order (children first)
        deletion_order = [
            (Deposit, "Deposit"),
            (Payment, "Payment"),
            (BillPayment, "BillPayment"),
            (RefundReceipt, "RefundReceipt"),
            (CreditMemo, "CreditMemo"),
            (VendorCredit, "VendorCredit"),
            (Invoice, "Invoice"),
            (SalesReceipt, "SalesReceipt"),
            (Bill, "Bill"),
            (Purchase, "Purchase"),
            (Transfer, "Transfer"),
            (JournalEntry, "JournalEntry"),
            (Estimate, "Estimate"),
            (PurchaseOrder, "PurchaseOrder"),
            (TimeActivity, "TimeActivity"),
        ]
        
        for TxnClass, class_name in deletion_order:
            logger.info(f"[CLEAN] Starting deletion of {class_name}...")
            try:
                records = TxnClass.all(qb=qb)
            except Exception as e:
                logger.error(f"[CLEAN] Failed to fetch {class_name}s: {e}")
                continue
                
            if not records:
                logger.info(f"[CLEAN] No {class_name}s found.")
                continue
                
            logger.info(f"[CLEAN] Found {len(records)} {class_name}(s) to delete.")
            to_retry = []
            
            for record in records:
                try:
                    logger.info(f"[CLEAN] Deleting {class_name} ID {record.Id}...")
                    record.delete(qb=qb)
                except QuickbooksException as qbe:
                    err_msg = str(qbe.message).lower()
                    logger.warning(f"[CLEAN] Error deleting {class_name} ID {record.Id}: {qbe.message}")
                    
                    if "stale" in err_msg or "sync" in err_msg or "token" in err_msg:
                        try:
                            logger.info(f"[CLEAN] Refetching {class_name} ID {record.Id} to resolve stale token...")
                            refetched = TxnClass.get(record.Id, qb=qb)
                            refetched.delete(qb=qb)
                            logger.info(f"[CLEAN] Successfully deleted refetched {class_name} ID {record.Id}")
                            continue
                        except Exception as refetch_err:
                            logger.error(f"[CLEAN] Refetch delete failed for {class_name} ID {record.Id}: {refetch_err}")
                    
                    if "linked" in err_msg or "link" in err_msg:
                        logger.info(f"[CLEAN] Postponing {class_name} ID {record.Id} for retry later due to link...")
                        to_retry.append(record)
                    else:
                        to_retry.append(record)
                except Exception as e:
                    logger.error(f"[CLEAN] Unexpected error deleting {class_name} ID {record.Id}: {e}")
                    to_retry.append(record)
            
            # Retry cycle
            if to_retry:
                logger.info(f"[CLEAN] Retrying {len(to_retry)} postponed {class_name}(s)...")
                for record in to_retry:
                    try:
                        logger.info(f"[CLEAN] Retrying deletion of {class_name} ID {record.Id}...")
                        refetched = TxnClass.get(record.Id, qb=qb)
                        refetched.delete(qb=qb)
                        logger.info(f"[CLEAN] Successfully deleted {class_name} ID {record.Id} on retry")
                    except Exception as e:
                        logger.error(f"[CLEAN] Retry deletion failed for {class_name} ID {record.Id}: {e}")

        # 2. Deactivate landscaping-specific accounts (sparse update Active: false)
        try:
            logger.info("[CLEAN] Fetching all accounts to find accounts to deactivate...")
            all_accounts = Account.all(qb=qb)
            deactivate_names = {
                "Design income",
                "Landscaping Services",
                "Pest Control Services",
                "Sales of Product Income",
                "Fountains and Garden Lighting",
                "Plants and Soil",
                "Sprinklers and Drip Systems"
            }
            landscaping_services_id = None
            for acc in all_accounts:
                if acc.Name == "Landscaping Services":
                    landscaping_services_id = acc.Id
                    break

            to_deactivate = []
            for acc in all_accounts:
                is_target = False
                if acc.Name in deactivate_names:
                    is_target = True
                elif landscaping_services_id and acc.ParentRef and acc.ParentRef.value == landscaping_services_id:
                    is_target = True
                elif acc.FullyQualifiedName and acc.FullyQualifiedName.startswith("Landscaping Services:"):
                    is_target = True
                    
                if is_target and acc.Active:
                    to_deactivate.append(acc)

            logger.info(f"[CLEAN] Found {len(to_deactivate)} account(s) to deactivate.")
            for acc in to_deactivate:
                try:
                    logger.info(f"[CLEAN] Deactivating account '{acc.Name}' (ID {acc.Id})...")
                    sparse_acc = Account()
                    sparse_acc.Id = acc.Id
                    sparse_acc.SyncToken = acc.SyncToken
                    sparse_acc.Active = False
                    sparse_acc.sparse = True
                    sparse_acc.save(qb=qb)
                    logger.info(f"[CLEAN] Deactivated account '{acc.Name}' successfully.")
                except Exception as e:
                    logger.error(f"[CLEAN] Failed to deactivate account '{acc.Name}': {e}")
        except Exception as e:
            logger.error(f"[CLEAN] Error deactivating accounts: {e}")

        # 3. Re-pull P&L (2024-01-01 to today) and verify
        try:
            today_str = datetime.now(timezone.utc).date().isoformat()
            logger.info(f"[CLEAN] Verifying clean state. Re-pulling P&L from 2024-01-01 to {today_str}...")
            
            pl_data = qb.get_report("ProfitAndLoss", qs={
                "start_date": "2024-01-01",
                "end_date": today_str,
                "summarize_column_by": "Month"
            })
            bs_data = qb.get_report("BalanceSheet", qs={
                "start_date": "2024-01-01",
                "end_date": today_str,
                "summarize_column_by": "Month"
            })
            
            today_date = datetime.now(timezone.utc).date()
            summary = parse_financial_summary(pl_data, bs_data, today_date)
            total_income = sum(m.total_revenue for m in summary.monthly_financials)
            total_expenses = sum(m.total_expenses for m in summary.monthly_financials)
            
            logger.info(f"[CLEAN] Verification totals: total_income = {total_income}, total_expenses = {total_expenses}")
            if total_income == Decimal("0") and total_expenses == Decimal("0"):
                logger.info("CLEAN COMPLETE")
            else:
                logger.info("NOT CLEAN")
                
            # Proactively update local snapshots
            try:
                from backend.app.services.sync import sync_tenant
                logger.info(f"[CLEAN] Triggering local DB sync for tenant {tenant_id}...")
                await sync_tenant(tenant_id, session)
                logger.info(f"[CLEAN] Local DB sync complete.")
            except Exception as se:
                logger.error(f"[CLEAN] Failed to run local DB sync: {se}")
                
        except Exception as e:
            logger.error(f"[CLEAN] Verification check failed: {e}")


async def run_qbo_seed_task(tenant_id: str, realm_id: str):
    logger.info(f"[SEED] Starting seed background task for tenant {tenant_id}, realm {realm_id}")
    from backend.app.database import _get_engine
    _, session_factory = _get_engine()
    
    # Jitter function
    def apply_jitter(amount: Decimal) -> Decimal:
        if amount == Decimal("0"):
            return Decimal("0")
        factor = 1 + random.uniform(-0.03, 0.03)
        val = round(float(amount) * factor, 2)
        return Decimal(str(val))
        
    async with session_factory() as session:
        try:
            qb = await get_qbo_client(realm_id=realm_id, tenant_id=tenant_id, session=session)
        except Exception as e:
            logger.error(f"[SEED] Failed to get QBO client: {e}")
            return
            
        # 1. Setup/get required accounts
        try:
            checking_account = get_or_create_account(qb, "Checking", "Bank", "Checking")
            subscription_revenue = get_or_create_account(qb, "Subscription Revenue", "Income", "SalesOfProductIncome")
            hosting_cogs = get_or_create_account(qb, "Hosting & Inference - COGS", "Cost of Goods Sold", "SuppliesMaterialsCogs")
            software_cloud = get_or_create_account(qb, "Software & Cloud", "Expense", "OtherMiscellaneousServiceCost")
            contractors = get_or_create_account(qb, "Contractors", "Expense", "OtherMiscellaneousServiceCost")
            salaries_wages = get_or_create_account(qb, "Salaries & Wages", "Expense", "PayrollExpenses")
            
            # Generic accounts synonyms/reuse
            advertising_account = get_or_create_account(qb, "Advertising", "Expense", "AdvertisingPromotional")
            insurance_account = get_or_create_account(qb, "Insurance", "Expense", "Insurance")
            legal_account = get_or_create_account(qb, "Legal & Professional", "Expense", "ProfessionalFees")
            rent_account = get_or_create_account(qb, "Rent", "Expense", "RentOrLease")
            utilities_account = get_or_create_account(qb, "Utilities", "Expense", "Utilities")
            office_account = get_or_create_account(qb, "Office Expenses", "Expense", "OfficeGeneralAdministrativeExpenses")
            
            # System accounts mapping
            opening_equity = get_or_create_account(qb, "Opening Balance Equity", "Equity", "RetainedEarnings")
            
            # Setup product/service item for subscription revenue
            subscription_item = get_or_create_item(qb, "Subscription", subscription_revenue)
            
            # Setup generic SaaS Customer
            saas_customer = get_or_create_customer(qb, "SaaS Subscriber")
            
        except Exception as e:
            logger.error(f"[SEED] Failed to setup accounts/items/customers: {e}")
            return

        # 2. Calibrated Params
        MRR_BY_MONTH = [0, 0, 2400, 3900, 5200, 5000, 7300, 9800, 11200, 10400, 13500, 16800, 19200, 22100]
        PARTIAL_JUNE_REVENUE = 5800
        HOSTING_COGS_PCT = 0.30
        PAYROLL_BY_MONTH = [26000, 27000, 28000, 30000, 30000, 33000, 38000, 38000, 42000, 42000, 48000, 50000, 52000, 54000]
        PARTIAL_JUNE_PAYROLL = 14000
        CLOUD_BASE = [800, 900, 1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800, 6500, 1900, 2000]  # idx 11 = anomaly (Apr 2026)
        SOFTWARE_TOOLS = 950
        RENT_FROM_MONTH_3 = 1800
        MARKETING_LUMPY = [0, 0, 500, 800, 1200, 900, 1500, 2000, 1800, 1200, 2500, 2200, 3000, 2500]
        CONTRACTORS_LUMPY = [0, 3500, 0, 4200, 0, 0, 5800, 0, 3000, 0, 0, 6100, 0, 2400]
        LEGAL = [0, 0, 0, 0, 0, 4800, 0, 0, 0, 0, 0, 0, 7200, 0]
        TARGET_RUNWAY_MONTHS = 10

        month_dates = []
        start_date = date(2025, 4, 1)
        for i in range(14):
            yr = start_date.year + (start_date.month - 1 + i) // 12
            mo = (start_date.month - 1 + i) % 12 + 1
            month_dates.append(date(yr, mo, 1))
            
        june_date = date(2026, 6, 8)

        # 3. Simulate and calculate exact starting cash in memory
        history = []
        
        # 14 Full Months
        for m in range(14):
            m_date = month_dates[m]
            m_date_str = m_date.isoformat()
            
            m_txns = []
            
            # Revenue (SalesReceipt)
            rev_val = Decimal(str(MRR_BY_MONTH[m]))
            if rev_val > 0:
                m_txns.append({
                    "type": "SalesReceipt",
                    "amount": rev_val,
                    "date": m_date_str,
                    "account": subscription_revenue,
                    "item": subscription_item,
                    "memo": f"[SEED] Subscription Revenue - {m_date.strftime('%B %Y')}"
                })
                
                # COGS (Purchase)
                cogs_val = apply_jitter(rev_val * Decimal(str(HOSTING_COGS_PCT)))
                m_txns.append({
                    "type": "Purchase",
                    "amount": cogs_val,
                    "date": m_date_str,
                    "account": hosting_cogs,
                    "memo": f"[SEED] Hosting COGS - {m_date.strftime('%B %Y')}"
                })
            
            # Expenses (Purchases)
            # Payroll
            m_txns.append({
                "type": "Purchase",
                "amount": Decimal(str(PAYROLL_BY_MONTH[m])),
                "date": m_date_str,
                "account": salaries_wages,
                "memo": f"[SEED] Payroll - {m_date.strftime('%B %Y')}"
            })
            
            # Cloud base: swap idx 11 and idx 12 to assign the anomaly value to April 2026
            if m == 11:
                cloud_base_val = Decimal(str(CLOUD_BASE[12]))
                cloud_memo = f"[SEED] Cloud base - {m_date.strftime('%B %Y')}"
            elif m == 12:
                cloud_base_val = Decimal(str(CLOUD_BASE[11]))
                cloud_memo = "[SEED] Cloud egress spike - one-off"
            else:
                cloud_base_val = Decimal(str(CLOUD_BASE[m]))
                cloud_memo = f"[SEED] Cloud base - {m_date.strftime('%B %Y')}"
                
            cloud_val = apply_jitter(cloud_base_val)
            m_txns.append({
                "type": "Purchase",
                "amount": cloud_val,
                "date": m_date_str,
                "account": software_cloud,
                "memo": cloud_memo
            })
            
            # Software tools
            soft_val = apply_jitter(Decimal(str(SOFTWARE_TOOLS)))
            m_txns.append({
                "type": "Purchase",
                "amount": soft_val,
                "date": m_date_str,
                "account": software_cloud,
                "memo": f"[SEED] Software tools - {m_date.strftime('%B %Y')}"
            })
            
            # Rent
            if m >= 2:
                rent_val = apply_jitter(Decimal(str(RENT_FROM_MONTH_3)))
                m_txns.append({
                    "type": "Purchase",
                    "amount": rent_val,
                    "date": m_date_str,
                    "account": rent_account,
                    "memo": f"[SEED] Office Rent - {m_date.strftime('%B %Y')}"
                })
                
            # Marketing
            mkt_base = Decimal(str(MARKETING_LUMPY[m]))
            if mkt_base > 0:
                m_txns.append({
                    "type": "Purchase",
                    "amount": apply_jitter(mkt_base),
                    "date": m_date_str,
                    "account": advertising_account,
                    "memo": f"[SEED] Marketing campaigns - {m_date.strftime('%B %Y')}"
                })
                
            # Contractors
            con_base = Decimal(str(CONTRACTORS_LUMPY[m]))
            if con_base > 0:
                m_txns.append({
                    "type": "Purchase",
                    "amount": apply_jitter(con_base),
                    "date": m_date_str,
                    "account": contractors,
                    "memo": f"[SEED] External Contractors - {m_date.strftime('%B %Y')}"
                })
                
            # Legal
            leg_base = Decimal(str(LEGAL[m]))
            if leg_base > 0:
                m_txns.append({
                    "type": "Purchase",
                    "amount": apply_jitter(leg_base),
                    "date": m_date_str,
                    "account": legal_account,
                    "memo": f"[SEED] Legal advisory fees - {m_date.strftime('%B %Y')}"
                })
                
            history.append((m_date, m_txns))

        # Month 15: Partial June
        june_txns = []
        june_rev = Decimal(str(PARTIAL_JUNE_REVENUE))
        june_txns.append({
            "type": "SalesReceipt",
            "amount": june_rev,
            "date": june_date.isoformat(),
            "account": subscription_revenue,
            "item": subscription_item,
            "memo": f"[SEED] Subscription Revenue - Partial June 2026"
        })
        june_cogs = apply_jitter(june_rev * Decimal(str(HOSTING_COGS_PCT)))
        june_txns.append({
            "type": "Purchase",
            "amount": june_cogs,
            "date": june_date.isoformat(),
            "account": hosting_cogs,
            "memo": f"[SEED] Hosting COGS - Partial June 2026"
        })
        june_txns.append({
            "type": "Purchase",
            "amount": Decimal(str(PARTIAL_JUNE_PAYROLL)),
            "date": june_date.isoformat(),
            "account": salaries_wages,
            "memo": f"[SEED] Payroll - Partial June 2026"
        })
        history.append((june_date, june_txns))

        # 4. Calculate Net Burn of latest full month (May 2026, index 13)
        may_txns = history[13][1]
        may_revenue = sum(t["amount"] for t in may_txns if t["type"] == "SalesReceipt")
        may_expenses = sum(t["amount"] for t in may_txns if t["type"] == "Purchase")
        may_net_burn = may_expenses - may_revenue
        
        target_ending_cash = TARGET_RUNWAY_MONTHS * may_net_burn
        
        # Calculate Total Net Income of the history
        total_revenue = Decimal("0")
        total_expenses = Decimal("0")
        for month_d, txns in history:
            total_revenue += sum(t["amount"] for t in txns if t["type"] == "SalesReceipt")
            total_expenses += sum(t["amount"] for t in txns if t["type"] == "Purchase")
            
        total_net_income = total_revenue - total_expenses
        starting_cash = target_ending_cash - total_net_income
        starting_cash = round(starting_cash, 2)
        
        logger.info(f"[SEED] Simulations: may_revenue = {may_revenue}, may_expenses = {may_expenses}, may_net_burn = {may_net_burn}")
        logger.info(f"[SEED] target_ending_cash = {target_ending_cash}, total_net_income = {total_net_income}")
        logger.info(f"[SEED] Back-solved starting_cash = {starting_cash}")

        # 5. Create Opening Deposit
        try:
            logger.info(f"[SEED] Creating starting cash deposit of ${starting_cash:,.2f} dated 2025-04-01...")
            dep = Deposit()
            dep.DepositToAccountRef = checking_account.to_ref()
            dep.TxnDate = "2025-04-01"
            dep.PrivateNote = "[SEED] Opening operating cash"
            
            line = DepositLine()
            line.Amount = starting_cash
            line.Description = "[SEED] Opening operating cash"
            line.DetailType = "DepositLineDetail"
            
            detail = DepositLineDetail()
            detail.AccountRef = opening_equity.to_ref()
            line.DepositLineDetail = detail
            
            dep.Line = [line]
            dep.save(qb=qb)
            logger.info("[SEED] Starting cash deposit created successfully.")
        except Exception as e:
            logger.error(f"[SEED] Failed to create opening deposit: {e}")
            return

        # 6. Write history to QBO
        for month_d, txns in history:
            month_label = month_d.strftime("%B %Y")
            logger.info(f"[SEED] Seeding transactions for {month_label}...")
            
            for txn in txns:
                try:
                    if txn["type"] == "SalesReceipt":
                        sr = SalesReceipt()
                        sr.DepositToAccountRef = checking_account.to_ref()
                        sr.CustomerRef = saas_customer.to_ref()
                        sr.TxnDate = txn["date"]
                        sr.PrivateNote = txn["memo"]
                        
                        sr_line = SalesItemLine()
                        sr_line.Amount = txn["amount"]
                        sr_line.DetailType = "SalesItemLineDetail"
                        sr_line.Description = txn["memo"]
                        
                        detail = SalesItemLineDetail()
                        detail.ItemRef = txn["item"].to_ref()
                        detail.Qty = 1
                        detail.UnitPrice = txn["amount"]
                        sr_line.SalesItemLineDetail = detail
                        
                        sr.Line = [sr_line]
                        sr.save(qb=qb)
                        
                    elif txn["type"] == "Purchase":
                        p = Purchase()
                        p.AccountRef = checking_account.to_ref()
                        p.PaymentType = "Cash"
                        p.TxnDate = txn["date"]
                        p.PrivateNote = txn["memo"]
                        
                        p_line = AccountBasedExpenseLine()
                        p_line.Amount = txn["amount"]
                        p_line.DetailType = "AccountBasedExpenseLineDetail"
                        p_line.Description = txn["memo"]
                        
                        detail = AccountBasedExpenseLineDetail()
                        detail.AccountRef = txn["account"].to_ref()
                        p_line.AccountBasedExpenseLineDetail = detail
                        
                        p.Line = [p_line]
                        p.save(qb=qb)
                        
                except Exception as e:
                    logger.error(f"[SEED] Failed to seed transaction {txn['memo']} dated {txn['date']}: {e}")
                    
        # 7. Verification
        try:
            logger.info("[SEED] Seeding finished. Starting verification...")
            today_str = june_date.isoformat()
            
            pl_data = qb.get_report("ProfitAndLoss", qs={
                "start_date": "2025-04-01",
                "end_date": today_str,
                "summarize_column_by": "Month"
            })
            bs_data = qb.get_report("BalanceSheet", qs={
                "start_date": "2025-04-01",
                "end_date": today_str,
                "summarize_column_by": "Month"
            })
            
            summary = parse_financial_summary(pl_data, bs_data, june_date)
            
            logger.info(f"[SEED] Asserting monthly revenues match inputs. Monthly financials found: {len(summary.monthly_financials)}")
            
            assert len(summary.monthly_financials) >= 15, f"Expected at least 15 months, got {len(summary.monthly_financials)}"
            summary.monthly_financials.sort(key=lambda x: x.month_start)
            
            assert summary.monthly_financials[0].total_revenue == Decimal("0"), "Month 1 revenue not 0"
            assert summary.monthly_financials[1].total_revenue == Decimal("0"), "Month 2 revenue not 0"
            
            for i in range(14):
                expected_rev = Decimal(str(MRR_BY_MONTH[i]))
                actual_rev = summary.monthly_financials[i].total_revenue
                assert actual_rev == expected_rev, f"Month {i+1} revenue mismatch: expected {expected_rev}, got {actual_rev}"
                
            actual_june_rev = summary.monthly_financials[14].total_revenue
            assert actual_june_rev == Decimal(str(PARTIAL_JUNE_REVENUE)), f"June revenue mismatch: expected {PARTIAL_JUNE_REVENUE}, got {actual_june_rev}"
            
            logger.info("[SEED] Verification: Monthly revenue assertions PASSED.")
            
            # Compute May 2026 metrics
            may_financial = summary.monthly_financials[13]
            current_mrr_run_rate = may_financial.total_revenue * Decimal("12")
            gross_burn = may_financial.total_expenses
            net_burn = may_financial.total_expenses - may_financial.total_revenue
            cash = summary.current_cash_balance
            runway = cash / net_burn if net_burn > 0 else Decimal("999")
            
            # Find COGS for May 2026
            pl_rows = pl_data.get("Rows", {}).get("Row", [])
            columns = pl_data.get("Columns", {}).get("Column", [])
            
            may_col_idx = None
            for idx, col in enumerate(columns):
                title = col.get("ColTitle") or col.get("colTitle") or ""
                d = parse_qbo_column_date(str(title))
                if d and d.year == 2026 and d.month == 5:
                    may_col_idx = idx
                    break
                    
            if may_col_idx is not None:
                from backend.app.tools.qbo_parser import _find_group_value_for_col
                may_cogs = _find_group_value_for_col(pl_rows, "COGS", may_col_idx)
                gross_margin = (may_financial.total_revenue - may_cogs) / may_financial.total_revenue if may_financial.total_revenue > 0 else Decimal("0")
            else:
                gross_margin = Decimal("0.70")
                
            total_net_burn = sum(m.total_expenses - m.total_revenue for m in summary.monthly_financials)
            ending_arr = current_mrr_run_rate
            burn_multiple = total_net_burn / ending_arr if ending_arr > 0 else Decimal("0")
            
            # Log metrics
            logger.info(f"[SEED] Metrics:")
            logger.info(f"  Current MRR Run-rate (ARR proxy): ${current_mrr_run_rate:,.2f}")
            logger.info(f"  Gross Burn: ${gross_burn:,.2f}")
            logger.info(f"  Net Burn: ${net_burn:,.2f}")
            logger.info(f"  Cash: ${cash:,.2f}")
            logger.info(f"  Runway: {runway:.2f} months")
            logger.info(f"  Gross Margin: {gross_margin * 100:.2f}%")
            logger.info(f"  Burn Multiple: {burn_multiple:.2f}")
            
            # Asserts
            assert Decimal("0.65") <= gross_margin <= Decimal("0.72"), f"Gross margin {gross_margin} not in [0.65, 0.72]"
            assert Decimal("2.0") <= burn_multiple <= Decimal("2.6"), f"Burn multiple {burn_multiple} not in [2.0, 2.6]"
            assert abs(runway - Decimal("10")) <= Decimal("1.5"), f"Runway {runway} is not close to 10"
            logger.info("[SEED] Verification: Metric assertions PASSED.")
            
            # Log naive-vs-correct run-rate gap (bug #13)
            naive_mrr_run_rate = summary.monthly_financials[14].total_revenue * Decimal("12")
            correct_mrr_run_rate = current_mrr_run_rate
            gap_mrr = correct_mrr_run_rate - naive_mrr_run_rate
            
            from backend.app.tools.run_rate import calculate_run_rate
            res_naive = calculate_run_rate.invoke({"summary": summary})
            summary_without_june = FinancialSummary(
                current_cash_balance=cash,
                monthly_financials=summary.monthly_financials[:-1]
            )
            res_correct = calculate_run_rate.invoke({"summary": summary_without_june})
            gap_tool = (res_correct.run_rate or Decimal("0")) - (res_naive.run_rate or Decimal("0"))
            
            logger.info("[SEED] Naive vs Correct Run-rate Gap (Bug #13) Details:")
            logger.info(f"  Naive MRR Run-rate (June annualized): ${naive_mrr_run_rate:,.2f}")
            logger.info(f"  Correct MRR Run-rate (May annualized): ${correct_mrr_run_rate:,.2f}")
            logger.info(f"  MRR Run-rate Gap: ${gap_mrr:,.2f}")
            logger.info(f"  Naive Tool Run-rate (includes June partial): ${res_naive.run_rate:,.2f}")
            logger.info(f"  Correct Tool Run-rate (excludes June partial): ${res_correct.run_rate:,.2f}")
            logger.info(f"  Tool Run-rate Gap: ${gap_tool:,.2f}")
            
            # Trigger sync of local DB
            try:
                from backend.app.services.sync import sync_tenant
                logger.info(f"[SEED] Triggering local DB sync for tenant {tenant_id}...")
                await sync_tenant(tenant_id, session)
                logger.info(f"[SEED] Local DB sync complete.")
            except Exception as se:
                logger.error(f"[SEED] Failed to run local DB sync: {se}")
                
        except AssertionError as ae:
            logger.error(f"[SEED] Verification assertion failed: {ae}", exc_info=True)
        except Exception as e:
            logger.error(f"[SEED] Verification check failed: {e}", exc_info=True)


# --- Endpoint Routes ---

@router.post("/qbo/clean")
async def clean_qbo(
    confirm: bool | None = Query(None),
    tenant_id: str | None = Query(None),
    realm_id: str | None = Query(None),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    session: AsyncSession = Depends(get_session)
):
    """Clean the QBO sandbox by deleting all transactions and deactivating landscaping accounts."""
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Confirmation required. Set query parameter confirm=true."
        )
        
    # Resolve target integration
    stmt = select(Integration).where(Integration.provider == "quickbooks")
    if tenant_id and realm_id:
        stmt = stmt.where(
            Integration.tenant_id == tenant_id,
            Integration.provider_connection_id == realm_id
        )
    elif tenant_id:
        stmt = stmt.where(Integration.tenant_id == tenant_id)
    elif realm_id:
        stmt = stmt.where(Integration.provider_connection_id == realm_id)
    else:
        stmt = stmt.where(Integration.sync_status.in_(["active", "error"]))
        
    res = await session.execute(stmt)
    integration = res.scalars().first()
    
    if not integration:
        raise HTTPException(status_code=404, detail="No active QuickBooks integration found.")
        
    background_tasks.add_task(
        run_qbo_clean_task,
        tenant_id=str(integration.tenant_id),
        realm_id=str(integration.provider_connection_id)
    )
    
    return JSONResponse(status_code=202, content={"message": "clean started"})


@router.post("/qbo/seed")
async def seed_qbo(
    tenant_id: str | None = Query(None),
    realm_id: str | None = Query(None),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    session: AsyncSession = Depends(get_session)
):
    """Seed a 15-month SaaS financial history in the QBO sandbox."""
    # Resolve target integration
    stmt = select(Integration).where(Integration.provider == "quickbooks")
    if tenant_id and realm_id:
        stmt = stmt.where(
            Integration.tenant_id == tenant_id,
            Integration.provider_connection_id == realm_id
        )
    elif tenant_id:
        stmt = stmt.where(Integration.tenant_id == tenant_id)
    elif realm_id:
        stmt = stmt.where(Integration.provider_connection_id == realm_id)
    else:
        stmt = stmt.where(Integration.sync_status.in_(["active", "error"]))
        
    res = await session.execute(stmt)
    integration = res.scalars().first()
    
    if not integration:
        raise HTTPException(status_code=404, detail="No active QuickBooks integration found.")
        
    # Get QBO Client for synchronous guards
    try:
        qb = await get_qbo_client(
            realm_id=str(integration.provider_connection_id),
            tenant_id=str(integration.tenant_id),
            session=session
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to initialize QuickBooks client: {str(e)}")
        
    # Guard 1: First re-pull P&L; if not empty, return 409
    today_str = datetime.now(timezone.utc).date().isoformat()
    try:
        pl_data = qb.get_report("ProfitAndLoss", qs={"start_date": "2024-01-01", "end_date": today_str})
        bs_data = qb.get_report("BalanceSheet", qs={"start_date": "2024-01-01", "end_date": today_str})
        today_date = datetime.now(timezone.utc).date()
        summary = parse_financial_summary(pl_data, bs_data, today_date)
        
        total_income = sum(m.total_revenue for m in summary.monthly_financials)
        total_expenses = sum(m.total_expenses for m in summary.monthly_financials)
        
        if total_income != Decimal("0") or total_expenses != Decimal("0"):
            raise HTTPException(status_code=409, detail="books not empty, run clean first")
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Error checking P&L empty guard: {e}")
        # If reports cannot be fetched, we continue, or raise 502
        raise HTTPException(status_code=502, detail=f"Upstream QuickBooks communication failed: {str(e)}")
    # Launch background task
    background_tasks.add_task(
        run_qbo_seed_task,
        tenant_id=str(integration.tenant_id),
        realm_id=str(integration.provider_connection_id)
    )
    
    return JSONResponse(status_code=202, content={"message": "seed started"})


@router.post("/trigger-computed-metrics")
async def trigger_computed_metrics():
    from backend.app.services.computed_metrics import run_daily_computed_metrics
    await run_daily_computed_metrics()
    return {"status": "done"}
