from sqlalchemy.orm import Session
from .. import models, schemas

def create_default_chart_of_accounts(db: Session, business_id: int):
    """
    Seeds a new business with a standard Chart of Accounts.
    This should be called within the same transaction as business creation.
    """
    default_accounts = [
        # Assets
        {"name": "Cash", "type": models.AccountType.ASSET, "is_system_account": True},
        # {"name": "Bank", "type": models.AccountType.ASSET, "is_system_account": True},
        {"name": "Accounts Receivable", "type": models.AccountType.ASSET, "is_system_account": True},
        {"name": "Inventory", "type": models.AccountType.ASSET, "is_system_account": True},
        {"name": "VAT Receivable (Input VAT)", "type": models.AccountType.ASSET, "is_system_account": True, "description": "Tracks VAT paid on purchases and expenses that can be reclaimed."},

        # Liabilities
        {"name": "Accounts Payable", "type": models.AccountType.LIABILITY, "is_system_account": True},
        {"name": "Payroll Liabilities", "type": models.AccountType.LIABILITY, "is_system_account": True},
        {"name": "PAYE Payable", "type": models.AccountType.LIABILITY, "is_system_account": True, "description": "Holds tax deducted from employees, awaiting remittance."},
        {"name": "Pension Payable", "type": models.AccountType.LIABILITY, "is_system_account": True, "description": "Holds employee and employer pension contributions, awaiting remittance."},
        {"name": "VAT Payable (Output VAT)", "type": models.AccountType.LIABILITY, "is_system_account": True, "description": "Tracks VAT collected from sales, owed to the government."},

        # Equity
        {"name": "Owner's Equity", "type": models.AccountType.EQUITY, "is_system_account": True},
        # Revenue
        {"name": "Sales Revenue", "type": models.AccountType.REVENUE, "is_system_account": True},
        {"name": "Other Income", "type": models.AccountType.REVENUE, "is_system_account": True},
        # Expenses
        {"name": "Cost of Goods Sold", "type": models.AccountType.EXPENSE, "is_system_account": True},
        {"name": "Salary Expense", "type": models.AccountType.EXPENSE, "is_system_account": True},
        {"name": "Office Use Expense", "type": models.AccountType.EXPENSE, "is_system_account": False},
        {"name": "Miscellaneous  Expense", "type": models.AccountType.EXPENSE, "is_system_account": False},
    ]

    for acc_data in default_accounts:
        db_account = models.Account(**acc_data, business_id=business_id)
        db.add(db_account)


def get_chart_of_accounts(db: Session, business_id: int):
    """
    Retrieves all accounts for a specific business, ordered by type and name.
    """
    return db.query(models.Account)\
        .filter(models.Account.business_id == business_id)\
        .order_by(models.Account.type, models.Account.name)\
        .all()



def get_account_by_id(db: Session, account_id: int, business_id: int):
    """Gets a single account by ID, ensuring it belongs to the correct business."""
    return db.query(models.Account).filter(
        models.Account.id == account_id,
        models.Account.business_id == business_id
    ).first()

def create_account(db: Session, account: schemas.AccountCreate, business_id: int):
    """Creates a new, non-system account for a business."""
    db_account = models.Account(
        name=account.name,
        type=account.type,
        business_id=business_id,
        is_system_account=False 
    )
    db.add(db_account)
    db.commit()
    db.refresh(db_account)
    return db_account


def update_account(db: Session, account_id: int, account_update: schemas.AccountUpdate, business_id: int):
    """Updates a user-created account's name."""
    db_account = get_account_by_id(db, account_id=account_id, business_id=business_id)
    if not db_account or db_account.is_system_account:
        return None # Cannot update system accounts

    db_account.name = account_update.name
    db.commit()
    db.refresh(db_account)
    return db_account


def can_delete_account(db: Session, account_id: int) -> bool:
    """
    Checks if an account has any associated ledger entries.
    Returns True if it's safe to delete, False otherwise.
    """
    entry_count = db.query(models.LedgerEntry).filter(models.LedgerEntry.account_id == account_id).count()
    return entry_count == 0


def delete_account(db: Session, account_id: int, business_id: int):
    """Deletes a user-created account if it has no transactions."""
    db_account = get_account_by_id(db, account_id=account_id, business_id=business_id)
    if not db_account or db_account.is_system_account:
        return False

    if not can_delete_account(db, account_id=account_id):
        return False 

    db.delete(db_account)
    db.commit()
    return True

