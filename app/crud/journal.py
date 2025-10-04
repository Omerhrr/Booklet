
from sqlalchemy.orm import Session
from sqlalchemy import desc
from .. import models
from datetime import date
from typing import List, Dict



def get_next_journal_voucher_number(db: Session, business_id: int) -> str:
    """Calculates the next sequential journal voucher number for a given business."""
    last_voucher = db.query(models.JournalVoucher.voucher_number)\
        .filter(models.JournalVoucher.business_id == business_id)\
        .order_by(desc(models.JournalVoucher.id))\
        .first()

    if not last_voucher:
        return "JV-0001"

    last_num = int(last_voucher[0].split('-')[-1])
    new_num = last_num + 1
    return f"JV-{new_num:04d}"

def create_journal_voucher(db: Session, business_id: int, branch_id: int, transaction_date: date, description: str, entries: List[Dict]):
    """
    Creates a new Journal Voucher and its associated, balanced ledger entries.
    """
    total_debits = sum(float(e.get('debit', 0) or 0) for e in entries)
    total_credits = sum(float(e.get('credit', 0) or 0) for e in entries)

    # Crucial validation: Ensure the entry is balanced
    if not (0.009 > total_debits - total_credits > -0.009): # Allow for minor floating point discrepancies
        raise ValueError(f"Journal entry is not balanced. Debits ({total_debits}) must equal Credits ({total_credits}).")

    # Create the parent voucher
    new_voucher = models.JournalVoucher(
        voucher_number=get_next_journal_voucher_number(db, business_id=business_id),
        transaction_date=transaction_date,
        description=description,
        business_id=business_id,
        branch_id=branch_id
    )
    db.add(new_voucher)
    db.flush() # To get the new_voucher.id

    # Create each ledger entry line
    for entry_data in entries:
        debit = float(entry_data.get('debit', 0) or 0)
        credit = float(entry_data.get('credit', 0) or 0)
        
        # Only create an entry if there's an amount
        if debit > 0 or credit > 0:
            db.add(models.LedgerEntry(
                transaction_date=transaction_date,
                description=description,
                debit=debit,
                credit=credit,
                account_id=int(entry_data['account_id']),
                branch_id=branch_id,
                journal_voucher_id=new_voucher.id
            ))
    
    return new_voucher

def get_journal_vouchers_by_branch(db: Session, business_id: int, branch_id: int):
    """Retrieves all Journal Vouchers for a specific branch."""
    return db.query(models.JournalVoucher)\
        .filter(
            models.JournalVoucher.business_id == business_id,
            models.JournalVoucher.branch_id == branch_id
        )\
        .order_by(desc(models.JournalVoucher.transaction_date))\
        .all()
