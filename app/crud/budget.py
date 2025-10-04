
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from .. import models, schemas
from datetime import date
import json

def get_budgets_by_branch(db: Session, branch_id: int):
    """Retrieves all budgets for a specific branch."""
    return db.query(models.Budget).filter(models.Budget.branch_id == branch_id).order_by(models.Budget.start_date.desc()).all()

def get_budget_by_id(db: Session, budget_id: int, branch_id: int):
    """Retrieves a single budget with its lines, ensuring it belongs to the correct branch."""
    return db.query(models.Budget).options(
        joinedload(models.Budget.lines).joinedload(models.BudgetLine.account)
    ).filter(
        models.Budget.id == budget_id,
        models.Budget.branch_id == branch_id
    ).first()

def create_budget(db: Session, name: str, branch_id: int, start_date: date, end_date: date, lines_json: str):
    """
    Creates a new budget and all its associated lines in a single transaction.
    """
    try:
        lines_data = json.loads(lines_json)
        
        with db.begin_nested():
            db_budget = models.Budget(
                name=name,
                branch_id=branch_id,
                start_date=start_date,
                end_date=end_date
            )
            db.add(db_budget)
            db.flush()

            for line_data in lines_data:
                account_id = line_data.get("account_id")
                amount = line_data.get("amount", 0.0)
                
                if account_id and float(amount) > 0:
                    db_line = models.BudgetLine(
                        budget_id=db_budget.id,
                        account_id=int(account_id),
                        amount=float(amount)
                    )
                    db.add(db_line)
        
        db.commit()
        return db_budget
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        db.rollback()
        print(f"Error creating budget: {e}")
        return None
    except Exception as e:
        db.rollback()
        print(f"An unexpected database error occurred: {e}")
        return None

def get_budget_vs_actual_report(db: Session, budget: models.Budget):
    """
    Generates a report comparing budgeted amounts to actual amounts from the ledger.
    """
    report_lines = []
    
    for line in budget.lines:
        # Determine the correct calculation based on account type
        if line.account.type == models.AccountType.REVENUE:
            # For Revenue: Actual = Credit - Debit
            actual_amount_query = db.query(func.sum(models.LedgerEntry.credit - models.LedgerEntry.debit))
        else: # Expense
            # For Expense: Actual = Debit - Credit
            actual_amount_query = db.query(func.sum(models.LedgerEntry.debit - models.LedgerEntry.credit))

        # Filter by account, branch, and the budget's date range
        actual_amount = actual_amount_query.filter(
            models.LedgerEntry.account_id == line.account_id,
            models.LedgerEntry.branch_id == budget.branch_id,
            models.LedgerEntry.transaction_date.between(budget.start_date, budget.end_date)
        ).scalar() or 0.0

        variance = actual_amount - line.amount
        
        # Calculate percentage, avoiding division by zero
        variance_percent = (variance / line.amount) * 100 if line.amount != 0 else 0
        
        report_lines.append({
            "account_name": line.account.name,
            "account_type": line.account.type,
            "budgeted_amount": line.amount,
            "actual_amount": actual_amount,
            "variance": variance,
            "variance_percent": variance_percent
        })
        
    return report_lines
