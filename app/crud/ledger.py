# app/crud/ledger.py
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, asc, func
from .. import models
from typing import Optional
from datetime import date
from .. import crud

def get_vendor_ledger(db: Session, vendor_id: int, business_id: int):
    """
    Retrieves all ledger entries for a specific vendor and calculates a running balance.
    """
    vendor = db.query(models.Vendor).filter_by(id=vendor_id, business_id=business_id).first()
    if not vendor:
        return [], 0.0

    entries = db.query(models.LedgerEntry)\
        .filter(models.LedgerEntry.vendor_id == vendor_id)\
        .order_by(asc(models.LedgerEntry.transaction_date), asc(models.LedgerEntry.id))\
        .all()

    running_balance = 0
    ledger_with_balance = []
    for entry in entries:
        if entry.account.name == 'Accounts Payable':
            running_balance += entry.credit - entry.debit
        
        ledger_with_balance.append({
            "entry": entry,
            "balance": running_balance
        })

    return ledger_with_balance, running_balance


def get_customer_ledger(db: Session, customer_id: int, business_id: int):
    """
    Retrieves all ledger entries for a specific customer and calculates a running balance.
    """
    customer = db.query(models.Customer).filter_by(id=customer_id, business_id=business_id).first()
    if not customer:
        return [], 0.0

    entries = db.query(models.LedgerEntry)\
        .filter(models.LedgerEntry.customer_id == customer_id)\
        .order_by(asc(models.LedgerEntry.transaction_date), asc(models.LedgerEntry.id))\
        .all()

    running_balance = 0
    ledger_with_balance = []
    for entry in entries:
        if entry.account.name == 'Accounts Receivable':
            running_balance += entry.debit - entry.credit
        
        ledger_with_balance.append({
            "entry": entry,
            "balance": running_balance
        })

    return ledger_with_balance, running_balance



def get_employee_ledger(db: Session, employee_id: int, business_id: int):
    """
    Retrieves all ledger entries related to an employee's payslips.
    """
    employee = db.query(models.Employee).filter_by(id=employee_id, business_id=business_id).first()
    if not employee:
        return []

    payslip_ids = [p.id for p in employee.payslips]

    if not payslip_ids:
        return []

    entries = db.query(models.LedgerEntry).options(
        joinedload(models.LedgerEntry.account)
    ).filter(
        models.LedgerEntry.payslip_id.in_(payslip_ids)
    ).order_by(
        asc(models.LedgerEntry.transaction_date),
        asc(models.LedgerEntry.id)
    ).all()

    return entries

def get_employee_ledger_summary(db: Session, employee_id: int, business_id: int):
    """
    Calculates summary KPIs for an employee's ledger history.
    """
    payslips = db.query(models.Payslip).filter_by(employee_id=employee_id).all()
    if not payslips:
        return {"total_net_pay": 0, "total_paye": 0, "total_pension": 0}

    total_net_pay = sum(p.net_pay for p in payslips)
    total_paye = sum(p.paye_deduction for p in payslips)
    total_pension = sum(p.pension_employee_deduction for p in payslips)

    return {
        "total_net_pay": total_net_pay,
        "total_paye": total_paye,
        "total_pension": total_pension
    }
def get_statutory_liability_ledger(db: Session, business_id: int, branch_id: int, account_name: str): # <-- Add branch_id
    """
    Fetches ledger entries and balance for a specific statutory account (PAYE or Pension)
    for a specific branch.
    """
    account = db.query(models.Account).filter_by(
        business_id=business_id, name=account_name
    ).first()
    
    if not account:
        return [], 0.0

    # THE FIX: Add branch_id to all queries
    entries = db.query(models.LedgerEntry).filter(
        models.LedgerEntry.account_id == account.id,
        models.LedgerEntry.branch_id == branch_id # <-- FILTER ADDED
    ).order_by(models.LedgerEntry.transaction_date.desc()).all()

    total_credits = db.query(func.sum(models.LedgerEntry.credit)).filter(
        models.LedgerEntry.account_id == account.id,
        models.LedgerEntry.branch_id == branch_id # <-- FILTER ADDED
    ).scalar() or 0.0
    
    total_debits = db.query(func.sum(models.LedgerEntry.debit)).filter(
        models.LedgerEntry.account_id == account.id,
        models.LedgerEntry.branch_id == branch_id # <-- FILTER ADDED
    ).scalar() or 0.0

    balance = total_credits - total_debits

    return entries, balance

def get_cashbook(db: Session, business_id: int, branch_id: int, start_date: Optional[date] = None, end_date: Optional[date] = None, account_id: Optional[int] = None):
    """
    Retrieves the cashbook for a specific branch and calculates a running balance.
    This is now enhanced to include all user-created bank accounts for the branch.
    """
    # THE FIX: Instead of querying by name, we get the IDs of all valid payment accounts.
    payment_accounts = crud.get_payment_accounts(db, business_id=business_id, branch_id=branch_id)
    account_ids = [acc.id for acc in payment_accounts]

    if not account_ids:
        return [], 0.0

    query = db.query(models.LedgerEntry).options(
        joinedload(models.LedgerEntry.account)
    ).filter(
        models.LedgerEntry.account_id.in_(account_ids),
        models.LedgerEntry.branch_id == branch_id
    ).order_by(
        models.LedgerEntry.transaction_date.asc(),
        models.LedgerEntry.id.asc()
    )

    if start_date:
        query = query.filter(models.LedgerEntry.transaction_date >= start_date)
    if end_date:
        query = query.filter(models.LedgerEntry.transaction_date <= end_date)
    
    # If a specific account is selected for filtering, we use it.
    if account_id:
        if account_id in account_ids:
            query = query.filter(models.LedgerEntry.account_id == account_id)
        else:
            # If the provided account_id is not a valid payment account, return nothing.
            return [], 0.0

    entries = query.all()

    running_balance = 0
    ledger_with_balance = []
    for entry in entries:
        running_balance += entry.debit - entry.credit
        ledger_with_balance.append({
            "entry": entry,
            "balance": running_balance
        })

    return ledger_with_balance, running_balance


def get_profit_and_loss_data(db: Session, business_id: int, start_date: date, end_date: date, branch_id: Optional[int] = None):
    """
    Calculates totals for Revenue and Expense accounts for a P&L statement.
    Can be filtered by a specific branch.
    """
    # **THE FIX IS HERE**: The nested function now accepts `branch_id`
    def get_balance_for_accounts(accounts, date_filter, branch_id_to_filter: Optional[int] = None):
        totals = {}
        total_balance = 0.0
        for acc in accounts:
            query_base = db.query(
                func.sum(models.LedgerEntry.credit - models.LedgerEntry.debit) if acc.type == models.AccountType.REVENUE else func.sum(models.LedgerEntry.debit - models.LedgerEntry.credit)
            ).filter(
                models.LedgerEntry.account_id == acc.id,
                date_filter
            )

            if branch_id_to_filter:
                query_base = query_base.filter(models.LedgerEntry.branch_id == branch_id_to_filter)
            
            balance = query_base.scalar() or 0.0
            totals[acc.name] = balance
            total_balance += balance
        return totals, total_balance

    date_filter = models.LedgerEntry.transaction_date.between(start_date, end_date)

    revenue_accounts = db.query(models.Account).filter_by(business_id=business_id, type=models.AccountType.REVENUE).all()
    expense_accounts = db.query(models.Account).filter_by(business_id=business_id, type=models.AccountType.EXPENSE).all()

    # **THE FIX IS HERE**: Pass the `branch_id` down to the helper function
    revenue_totals, total_revenue = get_balance_for_accounts(revenue_accounts, date_filter, branch_id_to_filter=branch_id)
    expense_totals, total_expenses = get_balance_for_accounts(expense_accounts, date_filter, branch_id_to_filter=branch_id)
        
    cogs = expense_totals.pop("Cost of Goods Sold", 0.0)
    gross_profit = total_revenue - cogs
    net_profit = gross_profit - sum(expense_totals.values())

    return {
        "revenue_totals": revenue_totals,
        "total_revenue": total_revenue,
        "cogs": cogs,
        "gross_profit": gross_profit,
        "operating_expenses": expense_totals,
        "total_operating_expenses": sum(expense_totals.values()),
        "net_profit": net_profit
    }


def get_general_ledger(db: Session, business_id: int, branch_id: int, start_date: Optional[date] = None, end_date: Optional[date] = None, account_id: Optional[int] = None):
    """
    Retrieves the general ledger for a specific branch, with optional filters.
    """
    query = db.query(models.LedgerEntry).join(models.Account).filter(
        models.Account.business_id == business_id,
        models.LedgerEntry.branch_id == branch_id
    ).options(
        joinedload(models.LedgerEntry.account)
    ).order_by(
        models.LedgerEntry.transaction_date.asc(),
        models.LedgerEntry.id.asc()
    )

    if start_date:
        query = query.filter(models.LedgerEntry.transaction_date >= start_date)
    if end_date:
        query = query.filter(models.LedgerEntry.transaction_date <= end_date)
    if account_id:
        query = query.filter(models.LedgerEntry.account_id == account_id)

    return query.all()


def get_balance_sheet_data(db: Session, business_id: int, as_of_date: date, branch_id: Optional[int] = None):
    """
    Calculates balances for Asset, Liability, and Equity accounts for a Balance Sheet.
    Can be filtered by a specific branch.
    """
    start_of_year = as_of_date.replace(month=1, day=1)
    pnl_data = get_profit_and_loss_data(db, business_id, start_of_year, as_of_date, branch_id=branch_id)
    net_profit_for_period = pnl_data.get("net_profit", 0.0)

    def get_account_balances(account_type: models.AccountType):
        accounts = db.query(models.Account).filter_by(business_id=business_id, type=account_type).all()
        
        balances = {}
        total = 0.0
        for acc in accounts:
            debit_query = db.query(func.sum(models.LedgerEntry.debit)).filter(
                models.LedgerEntry.account_id == acc.id,
                models.LedgerEntry.transaction_date <= as_of_date
            )
            credit_query = db.query(func.sum(models.LedgerEntry.credit)).filter(
                models.LedgerEntry.account_id == acc.id,
                models.LedgerEntry.transaction_date <= as_of_date
            )
            if branch_id:
                debit_query = debit_query.filter(models.LedgerEntry.branch_id == branch_id)
                credit_query = credit_query.filter(models.LedgerEntry.branch_id == branch_id)

            debit_sum = debit_query.scalar() or 0.0
            credit_sum = credit_query.scalar() or 0.0
            
            if account_type in [models.AccountType.ASSET, models.AccountType.EXPENSE]:
                balance = debit_sum - credit_sum
            else:
                balance = credit_sum - debit_sum

            if balance != 0:
                balances[acc.name] = balance
                total += balance
        return balances, total

    asset_balances, total_assets = get_account_balances(models.AccountType.ASSET)
    liability_balances, total_liabilities = get_account_balances(models.AccountType.LIABILITY)
    equity_balances, total_equity = get_account_balances(models.AccountType.EQUITY)

    equity_balances["Retained Earnings (Current Period)"] = net_profit_for_period
    total_equity += net_profit_for_period

    return {
        "assets": asset_balances,
        "total_assets": total_assets,
        "liabilities": liability_balances,
        "total_liabilities": total_liabilities,
        "equity": equity_balances,
        "total_equity": total_equity,
        "total_liabilities_and_equity": total_liabilities + total_equity
    }


def get_account_ledger(db: Session, account_id: int, branch_id: int, start_date: Optional[date] = None, end_date: Optional[date] = None):
    """
    Retrieves all ledger entries for a single, specific account in a branch
    and calculates a running balance.
    """
    query = db.query(models.LedgerEntry).filter(
        models.LedgerEntry.account_id == account_id,
        models.LedgerEntry.branch_id == branch_id
    ).order_by(
        models.LedgerEntry.transaction_date.asc(),
        models.LedgerEntry.id.asc()
    )

    if start_date:
        query = query.filter(models.LedgerEntry.transaction_date >= start_date)
    if end_date:
        query = query.filter(models.LedgerEntry.transaction_date <= end_date)

    entries = query.all()

    # Calculate opening balance
    opening_balance_query = db.query(func.sum(models.LedgerEntry.debit - models.LedgerEntry.credit)).filter(
        models.LedgerEntry.account_id == account_id,
        models.LedgerEntry.branch_id == branch_id
    )
    if start_date:
        opening_balance_query = opening_balance_query.filter(models.LedgerEntry.transaction_date < start_date)
    
    opening_balance = opening_balance_query.scalar() or 0.0

    running_balance = opening_balance
    ledger_with_balance = []
    for entry in entries:
        running_balance += entry.debit - entry.credit
        ledger_with_balance.append({
            "entry": entry,
            "balance": running_balance
        })

    return ledger_with_balance, opening_balance, running_balance



def create_vat_payment_entry(db: Session, business_id: int, branch_id: int, payment_date: date, amount_paid: float, payment_account_id: int, output_vat_total: float, input_vat_total: float):
    """
    Creates the ledger entries to record a VAT payment to the government.
    This clears the liability and receivable accounts for the period.
    """
    output_vat_account = db.query(models.Account).filter_by(business_id=business_id, name="VAT Payable (Output VAT)").first()
    input_vat_account = db.query(models.Account).filter_by(business_id=business_id, name="VAT Receivable (Input VAT)").first()

    if not output_vat_account or not input_vat_account:
        raise ValueError("VAT accounts are not configured for this business.")

    # Create the parent Journal Voucher for the transaction
    description = f"VAT payment for period ending {payment_date.strftime('%Y-%m-%d')}"
    new_voucher = models.JournalVoucher(
        voucher_number=crud.journal.get_next_journal_voucher_number(db, business_id=business_id),
        transaction_date=payment_date,
        description=description,
        business_id=business_id,
        branch_id=branch_id
    )
    db.add(new_voucher)
    db.flush()

    # 1. Debit VAT Payable to clear the liability collected from sales
    db.add(models.LedgerEntry(
        transaction_date=payment_date, description=description, debit=output_vat_total,
        account_id=output_vat_account.id, branch_id=branch_id, journal_voucher_id=new_voucher.id
    ))

    # 2. Credit VAT Receivable to clear the asset from purchases
    db.add(models.LedgerEntry(
        transaction_date=payment_date, description=description, credit=input_vat_total,
        account_id=input_vat_account.id, branch_id=branch_id, journal_voucher_id=new_voucher.id
    ))

    # 3. Credit the Bank/Cash account for the actual amount paid out
    db.add(models.LedgerEntry(
        transaction_date=payment_date, description=description, credit=amount_paid,
        account_id=payment_account_id, branch_id=branch_id, journal_voucher_id=new_voucher.id
    ))

    return new_voucher