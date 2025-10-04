from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from .. import models
from datetime import date

def create_expense(db: Session, expense_data: dict):
    """
    Creates a new expense record and the correct, branch-aware ledger entries, including VAT.
    """
    business_id = expense_data['business_id']
    branch_id = expense_data['branch_id']
    business = db.query(models.Business).filter(models.Business.id == business_id).first()

    # Fetch necessary accounts
    expense_account = db.query(models.Account).filter_by(id=expense_data['expense_account_id'], business_id=business_id).first()
    paid_from_account = db.query(models.Account).filter_by(id=expense_data['paid_from_account_id'], business_id=business_id).first()
    vat_account = db.query(models.Account).filter_by(business_id=business_id, name="VAT Receivable (Input VAT)").first()

    if not expense_account or not paid_from_account:
        raise ValueError("A required account for this transaction could not be found.")
    if business.is_vat_registered and not vat_account:
        raise ValueError("VAT Receivable account not found for this VAT-registered business.")

    sub_total = expense_data['sub_total']
    vat_amount = expense_data['vat_amount'] if business.is_vat_registered else 0
    total_amount = sub_total + vat_amount

    new_expense = models.Expense(
        expense_number=get_next_expense_number(db, business_id=business_id),
        expense_date=expense_data['expense_date'],
        category=expense_account.name,
        sub_total=sub_total,
        vat_amount=vat_amount,
        amount=total_amount, # 'amount' now stores the grand total
        description=expense_data['description'],
        paid_from_account_id=expense_data['paid_from_account_id'],
        expense_account_id=expense_data['expense_account_id'],
        vendor_id=expense_data.get('vendor_id'),
        branch_id=branch_id, 
        business_id=business_id
    )
    db.add(new_expense)
    
    description = f"Expense {new_expense.expense_number}: {new_expense.description}"

    # --- UPDATED ACCOUNTING ENTRIES ---
    # 1. Debit the Expense account for the NET amount
    db.add(models.LedgerEntry(
        transaction_date=new_expense.expense_date, description=description,
        debit=sub_total, account_id=new_expense.expense_account_id, branch_id=branch_id, vendor_id=new_expense.vendor_id
    ))
    # 2. Debit VAT Receivable for the VAT amount
    if business.is_vat_registered and vat_amount > 0:
        db.add(models.LedgerEntry(
            transaction_date=new_expense.expense_date, description=f"Input VAT on {new_expense.expense_number}",
            debit=vat_amount, account_id=vat_account.id, branch_id=branch_id, vendor_id=new_expense.vendor_id
        ))
    # 3. Credit the payment account (Cash/Bank) for the FULL amount
    db.add(models.LedgerEntry(
        transaction_date=new_expense.expense_date, description=description,
        credit=total_amount, account_id=new_expense.paid_from_account_id, branch_id=branch_id, vendor_id=new_expense.vendor_id
    ))
    
    return new_expense

def get_expenses_by_business(db: Session, business_id: int):
    """
    Retrieves all expenses for a business, ordered by most recent.
    Eagerly loads related branch and vendor info to prevent extra queries.
    """
    return db.query(models.Expense)\
        .filter(models.Expense.business_id == business_id)\
        .options(
            joinedload(models.Expense.branch),
            joinedload(models.Expense.vendor)
        )\
        .order_by(desc(models.Expense.expense_date))\
        .all()


def get_expenses_by_branch(db: Session, business_id: int, branch_id: int): # Renamed for clarity
    """
    Retrieves all expenses for a specific branch, ordered by most recent.
    Eagerly loads related branch and vendor info to prevent extra queries.
    """
    return db.query(models.Expense)\
        .filter(
            models.Expense.business_id == business_id,
            models.Expense.branch_id == branch_id  
        )\
        .options(
            joinedload(models.Expense.branch),
            joinedload(models.Expense.vendor)
        )\
        .order_by(desc(models.Expense.expense_date))\
        .all()
def get_expense_accounts(db: Session, business_id: int):
    """
    Retrieves all accounts of type 'Expense' for a given business,
    to be used for populating the category dropdown.
    """
    return db.query(models.Account)\
        .filter(
            models.Account.business_id == business_id, 
            models.Account.type == models.AccountType.EXPENSE
        )\
        .order_by(models.Account.name)\
        .all()

def get_expense_by_id(db: Session, expense_id: int, business_id: int):
    """Fetches a single expense by its ID, ensuring it belongs to the business."""
    return db.query(models.Expense).filter(
        models.Expense.id == expense_id,
        models.Expense.business_id == business_id
    ).first()

def delete_expense_and_reverse_ledger(db: Session, expense: models.Expense):
    """
    Deletes an expense and creates a reversing entry in the general ledger.
    """
    reversal_description = f"Reversal of expense: {expense.description}"
    branch_id = expense.branch_id
    credit_reversal = models.LedgerEntry(
        transaction_date=date.today(), 
        description=reversal_description,
        credit=expense.amount,
        account_id=expense.expense_account_id,
        vendor_id=expense.vendor_id,
        branch_id=branch_id
    )
    debit_reversal = models.LedgerEntry(
        transaction_date=date.today(),
        description=reversal_description,
        debit=expense.amount,
        account_id=expense.paid_from_account_id,
        vendor_id=expense.vendor_id,
        branch_id=branch_id
    )
    
    db.add_all([credit_reversal, debit_reversal])
    db.delete(expense)

def get_next_expense_number(db: Session, business_id: int) -> str:
    """Calculates the next sequential expense number for a given business."""
    last_expense = db.query(models.Expense.expense_number)\
        .filter(models.Expense.business_id == business_id)\
        .order_by(desc(models.Expense.id))\
        .first()

    if not last_expense:
        return "EXP-0001"

    last_num = int(last_expense[0].split('-')[-1])
    new_num = last_num + 1
    return f"EXP-{new_num:04d}"


