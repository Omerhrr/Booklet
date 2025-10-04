
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, func
from .. import models, schemas
from datetime import date
from typing import List

def get_bank_accounts_by_branch(db: Session, branch_id: int):
    """Retrieves all user-created bank accounts for a specific branch."""
    return db.query(models.BankAccount).filter(models.BankAccount.branch_id == branch_id).order_by(models.BankAccount.account_name).all()

def create_bank_account(db: Session, account_data: schemas.BankAccountCreate, business_id: int, branch_id: int):
    """
    Creates a new Bank Account and its corresponding entry in the Chart of Accounts.
    This is a single transactional unit.
    """
    # 1. Create the entry in the main Chart of Accounts first.
    new_chart_of_account = models.Account(
        name=account_data.account_name,
        type=models.AccountType.ASSET,
        business_id=business_id,
        is_system_account=False # User-created
    )
    db.add(new_chart_of_account)
    db.flush() # To get the ID of the new account

    # 2. Create the detailed BankAccount record.
    new_bank_account = models.BankAccount(
        account_name=account_data.account_name,
        bank_name=account_data.bank_name,
        account_number=account_data.account_number,
        chart_of_account_id=new_chart_of_account.id,
        branch_id=branch_id,
        business_id=business_id
    )
    db.add(new_bank_account)
    db.commit()
    db.refresh(new_bank_account)
    return new_bank_account

def get_payment_accounts(db: Session, business_id: int, branch_id: int):
    """
    Retrieves all accounts that can be used for payments for a specific branch.
    This now includes the user-created Bank Accounts and the system 'Cash' account.
    """
    # Get user-created bank accounts for the branch by joining through the chart of accounts
    bank_accounts = db.query(models.Account).join(models.BankAccount).filter(
        models.BankAccount.branch_id == branch_id
    ).all()

    # Get the system 'Cash' account for the business
    cash_account = db.query(models.Account).filter(
        models.Account.business_id == business_id,
        models.Account.name == 'Cash',
        models.Account.is_system_account == True
    ).first()

    payment_accounts = bank_accounts
    if cash_account:
        payment_accounts.append(cash_account)
    
    return sorted(payment_accounts, key=lambda x: x.name)

def create_fund_transfer(db: Session, transfer_data: dict, business_id: int, branch_id: int):
    """
    Creates a new Fund Transfer record and the corresponding double-entry ledger postings.
    """
    from_account_id = transfer_data['from_account_id']
    to_account_id = transfer_data['to_account_id']
    amount = transfer_data['amount']
    
    if from_account_id == to_account_id:
        raise ValueError("From and To accounts cannot be the same.")
    if amount <= 0:
        raise ValueError("Transfer amount must be positive.")

    new_transfer = models.FundTransfer(
        transfer_date=transfer_data['transfer_date'],
        description=transfer_data['description'],
        amount=amount,
        from_account_id=from_account_id,
        to_account_id=to_account_id,
        branch_id=branch_id,
        business_id=business_id
    )
    db.add(new_transfer)
    db.flush()

    description = f"Fund Transfer: {new_transfer.description}"

    db.add(models.LedgerEntry(
        transaction_date=new_transfer.transfer_date,
        description=description,
        credit=amount,
        account_id=from_account_id,
        branch_id=branch_id,
        fund_transfer_id=new_transfer.id
    ))

    db.add(models.LedgerEntry(
        transaction_date=new_transfer.transfer_date,
        description=description,
        debit=amount,
        account_id=to_account_id,
        branch_id=branch_id,
        fund_transfer_id=new_transfer.id
    ))
    
    return new_transfer

def get_fund_transfers_by_branch(db: Session, business_id: int, branch_id: int):
    """Retrieves all Fund Transfer records for a specific branch."""
    return db.query(models.FundTransfer)\
        .filter(
            models.FundTransfer.business_id == business_id,
            models.FundTransfer.branch_id == branch_id
        )\
        .options(joinedload(models.FundTransfer.from_account), joinedload(models.FundTransfer.to_account))\
        .order_by(desc(models.FundTransfer.transfer_date))\
        .all()

def get_unreconciled_transactions(db: Session, account_id: int, branch_id: int):
    """
    Retrieves all ledger entries for a specific bank/cash account that have not yet been reconciled.
    """
    return db.query(models.LedgerEntry).filter(
        models.LedgerEntry.account_id == account_id,
        models.LedgerEntry.branch_id == branch_id,
        models.LedgerEntry.is_reconciled == False
    ).order_by(models.LedgerEntry.transaction_date.asc()).all()

def get_opening_balance_for_reconciliation(db: Session, account_id: int):
    """
    Calculates the opening balance for a new reconciliation.
    """
    balance = db.query(
        func.sum(models.LedgerEntry.debit - models.LedgerEntry.credit)
    ).filter(
        models.LedgerEntry.account_id == account_id,
        models.LedgerEntry.is_reconciled == True
    ).scalar()
    
    return balance or 0.0

def process_reconciliation(db: Session, business_id: int, branch_id: int, account_id: int, statement_date: date, statement_balance: float, cleared_transaction_ids: List[int]):
    """
    Finalizes a bank reconciliation. Creates the reconciliation record, updates all
    related ledger entries, and updates the bank account summary.
    """
    reconciliation = models.BankReconciliation(
        account_id=account_id,
        statement_date=statement_date,
        statement_balance=statement_balance,
        business_id=business_id,
        branch_id=branch_id
    )
    db.add(reconciliation)
    db.flush()

    if cleared_transaction_ids:
        db.query(models.LedgerEntry)\
            .filter(models.LedgerEntry.id.in_(cleared_transaction_ids))\
            .update({
                'is_reconciled': True,
                'reconciliation_id': reconciliation.id
            }, synchronize_session=False)
    
    # Update the summary on the BankAccount model
    db_bank_account = db.query(models.BankAccount).filter(models.BankAccount.chart_of_account_id == account_id).first()
    if db_bank_account:
        db_bank_account.last_reconciliation_date = statement_date
        db_bank_account.last_reconciliation_balance = statement_balance
        db.add(db_bank_account)
        
    return reconciliation

def get_reconciliation_report_data(db: Session, reconciliation_id: int, business_id: int):
    """Gathers all data needed for the post-reconciliation report."""
    reconciliation = db.query(models.BankReconciliation).filter(
        models.BankReconciliation.id == reconciliation_id,
        models.BankReconciliation.business_id == business_id
    ).options(
        joinedload(models.BankReconciliation.account) # Eager load the account info
    ).first()

    if not reconciliation:
        return None

    # Find the opening balance, which is the closing balance of the *previous* reconciliation for this account.
    previous_reconciliation = db.query(models.BankReconciliation).filter(
        models.BankReconciliation.account_id == reconciliation.account_id,
        models.BankReconciliation.statement_date < reconciliation.statement_date
    ).order_by(models.BankReconciliation.statement_date.desc()).first()

    book_starting_balance = previous_reconciliation.statement_balance if previous_reconciliation else 0.0

    # Get all transactions that were cleared in THIS reconciliation
    cleared_transactions = db.query(models.LedgerEntry).filter(
        models.LedgerEntry.reconciliation_id == reconciliation_id
    ).order_by(models.LedgerEntry.transaction_date).all()

    # Get all transactions for this account that were STILL not reconciled as of the statement date
    uncleared_transactions = db.query(models.LedgerEntry).filter(
        models.LedgerEntry.account_id == reconciliation.account_id,
        models.LedgerEntry.is_reconciled == False,
        models.LedgerEntry.transaction_date <= reconciliation.statement_date
    ).order_by(models.LedgerEntry.transaction_date).all()

    return {
        "reconciliation": reconciliation,
        "account": reconciliation.account,
        "book_starting_balance": book_starting_balance,
        "cleared_transactions": cleared_transactions,
        "uncleared_transactions": uncleared_transactions
    }