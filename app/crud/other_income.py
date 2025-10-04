
from sqlalchemy.orm import Session
from sqlalchemy import desc
from .. import models
from datetime import date

def get_next_income_number(db: Session, business_id: int) -> str:
    """Calculates the next sequential other income number."""
    last_income = db.query(models.OtherIncome.income_number)\
        .filter(models.OtherIncome.business_id == business_id)\
        .order_by(desc(models.OtherIncome.id))\
        .first()

    if not last_income:
        return "INC-0001"

    last_num = int(last_income[0].split('-')[-1])
    new_num = last_num + 1
    return f"INC-{new_num:04d}"

def create_other_income(db: Session, income_data: dict, business_id: int, branch_id: int):
    """
    Creates a new 'Other Income' record and the correct double-entry ledger postings.
    """
    # Create the OtherIncome record
    new_income = models.OtherIncome(
        income_number=get_next_income_number(db, business_id=business_id),
        income_date=income_data['income_date'],
        description=income_data['description'],
        amount=income_data['amount'],
        income_account_id=income_data['income_account_id'],
        deposited_to_account_id=income_data['deposited_to_account_id'],
        branch_id=branch_id,
        business_id=business_id
    )
    db.add(new_income)
    db.flush() # To get the new_income.id

    # 1. Debit the asset account (Cash/Bank) that received the money
    db.add(models.LedgerEntry(
        transaction_date=new_income.income_date,
        description=f"Other Income: {new_income.description}",
        debit=new_income.amount,
        account_id=new_income.deposited_to_account_id,
        branch_id=branch_id,
        other_income_id=new_income.id
    ))

    # 2. Credit the revenue account (e.g., "Interest Income")
    db.add(models.LedgerEntry(
        transaction_date=new_income.income_date,
        description=f"Other Income: {new_income.description}",
        credit=new_income.amount,
        account_id=new_income.income_account_id,
        branch_id=branch_id,
        other_income_id=new_income.id
    ))
    
    return new_income

def get_other_incomes_by_branch(db: Session, business_id: int, branch_id: int):
    """Retrieves all 'Other Income' records for a specific branch."""
    return db.query(models.OtherIncome)\
        .filter(
            models.OtherIncome.business_id == business_id,
            models.OtherIncome.branch_id == branch_id
        )\
        .order_by(desc(models.OtherIncome.income_date))\
        .all()

def get_other_income_accounts(db: Session, business_id: int):
    """
    Retrieves all accounts of type 'Revenue' for a given business,
    excluding the main 'Sales Revenue' account.
    """
    return db.query(models.Account)\
        .filter(
            models.Account.business_id == business_id, 
            models.Account.type == models.AccountType.REVENUE,
            models.Account.name != 'Sales Revenue'
        )\
        .order_by(models.Account.name)\
        .all()
