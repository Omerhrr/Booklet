from sqlalchemy.orm import Session, joinedload, subqueryload
from datetime import date
from .. import models, schemas
from typing import List
import math

def create_employee(db: Session, employee: schemas.EmployeeCreate, business_id: int):
    """
    Creates a new employee and their associated payroll configuration.
    This is a single transactional unit.
    """
    payroll_config_data = employee.payroll_config.model_dump()
    db_payroll_config = models.PayrollConfig(**payroll_config_data)
    employee_data = employee.model_dump(exclude={'payroll_config'})
    db_employee = models.Employee(**employee_data, business_id=business_id)
    db_employee.payroll_config = db_payroll_config
    db.add(db_employee)
    db.commit()
    db.refresh(db_employee)
    return db_employee

def get_employees_by_branch(db: Session, branch_id: int, is_active: bool = None):
    """
    Retrieves all employees for a specific branch, ordered by name.
    Can optionally filter by active status.
    """
    query = db.query(models.Employee).filter(models.Employee.branch_id == branch_id)
    if is_active is not None:
        query = query.filter(models.Employee.is_active == is_active)
    return query.order_by(models.Employee.full_name).all()

def get_employees_by_business(db: Session, business_id: int, is_active: bool = None):
    """
    Retrieves all employees for a specific business, ordered by name.
    Can optionally filter by active status.
    """
    query = db.query(models.Employee).filter(models.Employee.business_id == business_id)
    if is_active is not None:
        query = query.filter(models.Employee.is_active == is_active)
    return query.order_by(models.Employee.full_name).all()


def get_employee_by_id(db: Session, employee_id: int, business_id: int):
    """
    Gets a single employee by ID, ensuring it belongs to the correct business.
    Eagerly loads the payroll configuration to avoid extra queries.
    """
    return db.query(models.Employee).options(
        joinedload(models.Employee.payroll_config)
    ).filter(
        models.Employee.id == employee_id,
        models.Employee.business_id == business_id
    ).first()

def update_employee(db: Session, employee_id: int, employee_update: schemas.EmployeeUpdate, business_id: int):
    """
    Updates an employee's personal details.
    """
    db_employee = get_employee_by_id(db, employee_id=employee_id, business_id=business_id)
    if not db_employee:
        return None
    
    update_data = employee_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_employee, key, value)
        
    db.commit()
    db.refresh(db_employee)
    return db_employee

def update_payroll_config(db: Session, employee_id: int, payroll_update: schemas.PayrollConfigUpdate, business_id: int):
    """
    Updates an employee's payroll configuration.
    """
    db_employee = get_employee_by_id(db, employee_id=employee_id, business_id=business_id)
    if not db_employee or not db_employee.payroll_config:
        return None

    db_payroll_config = db_employee.payroll_config
    update_data = payroll_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_payroll_config, key, value)

    db.commit()
    db.refresh(db_employee)
    return db_employee

def update_employee_status(db: Session, employee_id: int, is_active: bool, business_id: int):
    """
    Updates an employee's active status and termination date.
    """
    db_employee = get_employee_by_id(db, employee_id=employee_id, business_id=business_id)
    if not db_employee:
        return None
    
    db_employee.is_active = is_active
    if not is_active:
        db_employee.termination_date = date.today()
    else:
        db_employee.termination_date = None
        
    db.commit()
    db.refresh(db_employee)
    return db_employee

def process_payroll_for_employee(
    db: Session,
    employee_id: int,
    business_id: int,
    pay_period_start: date,
    pay_period_end: date,
    additions: List[dict],
    deductions: List[dict]
):
    """
    Processes payroll for a single employee for a given period.
    This function should be called within a transaction.
    IT DOES NOT COMMIT.
    """
    employee = get_employee_by_id(db, employee_id=employee_id, business_id=business_id)
    if not employee or not employee.payroll_config:
        raise ValueError(f"Employee or payroll config not found for ID {employee_id}")

    branch_id = employee.branch_id
    config = employee.payroll_config
    
    salary_expense_account = db.query(models.Account).filter_by(business_id=business_id, name="Salary Expense").first()
    payroll_liabilities_account = db.query(models.Account).filter_by(business_id=business_id, name="Payroll Liabilities").first()
    paye_payable_account = db.query(models.Account).filter_by(business_id=business_id, name="PAYE Payable").first()
    pension_payable_account = db.query(models.Account).filter_by(business_id=business_id, name="Pension Payable").first()

    if not all([salary_expense_account, payroll_liabilities_account, paye_payable_account, pension_payable_account]):
        raise ValueError("Core payroll accounts are missing. Please check Chart of Accounts.")

    gross_pay = config.gross_salary
    total_additions = sum(item['amount'] for item in additions)
    taxable_income = gross_pay + total_additions
    
    paye_deduction = math.ceil(taxable_income * (config.paye_rate or 0.0))
    pension_employee_deduction = math.ceil(gross_pay * (config.pension_employee_rate or 0.0))
    pension_employer_contribution = math.ceil(gross_pay * (config.pension_employer_rate or 0.0))
    
    other_deductions = sum(item['amount'] for item in deductions)
    total_deductions = paye_deduction + pension_employee_deduction + other_deductions
    net_pay = taxable_income - total_deductions

    # **THE FIX IS HERE**: Correctly populate the Payslip model with all calculated values.
    db_payslip = models.Payslip(
        employee_id=employee.id,
        pay_period_start=pay_period_start,
        pay_period_end=pay_period_end,
        pay_date=date.today(),
        gross_pay=gross_pay,
        paye_deduction=paye_deduction,
        pension_employee_deduction=pension_employee_deduction,
        pension_employer_contribution=pension_employer_contribution,
        total_deductions=total_deductions,
        net_pay=net_pay
    )
    for item in additions:
        db_payslip.additions.append(models.PayslipAddition(**item))
    for item in deductions:
        db_payslip.deductions.append(models.PayslipDeduction(**item))
    db.add(db_payslip)
    db.flush()

    total_payroll_expense = gross_pay + total_additions + pension_employer_contribution
    
    db.add(models.LedgerEntry(
        transaction_date=date.today(),
        description=f"Payroll for {employee.full_name} ({pay_period_start} to {pay_period_end})",
        debit=total_payroll_expense, account_id=salary_expense_account.id, payslip_id=db_payslip.id, branch_id=branch_id
    ))
    db.add(models.LedgerEntry(
        transaction_date=date.today(), description=f"Net pay for {employee.full_name}",
        credit=net_pay, account_id=payroll_liabilities_account.id, payslip_id=db_payslip.id, branch_id=branch_id
    ))
    if paye_deduction > 0:
        db.add(models.LedgerEntry(
            transaction_date=date.today(), description=f"PAYE for {employee.full_name}",
            credit=paye_deduction, account_id=paye_payable_account.id, payslip_id=db_payslip.id, branch_id=branch_id
        ))
    total_pension_contribution = pension_employee_deduction + pension_employer_contribution
    if total_pension_contribution > 0:
        db.add(models.LedgerEntry(
            transaction_date=date.today(), description=f"Pension for {employee.full_name}",
            credit=total_pension_contribution, account_id=pension_payable_account.id, payslip_id=db_payslip.id, branch_id=branch_id
        ))
        
    return db_payslip

def get_payslips_by_business(db: Session, business_id: int):
    """
    Retrieves all payslips for a business, ordered by most recent pay date.
    """
    return db.query(models.Payslip).join(models.Employee).filter(
        models.Employee.business_id == business_id
    ).options(
        joinedload(models.Payslip.employee)
    ).order_by(models.Payslip.pay_date.desc()).all()

def get_payslip_by_id(db: Session, payslip_id: int, business_id: int):
    """
    Retrieves a single payslip by its ID, ensuring it belongs to the business.
    """
    return db.query(models.Payslip).join(models.Employee).filter(
        models.Payslip.id == payslip_id,
        models.Employee.business_id == business_id
    ).options(
        joinedload(models.Payslip.employee).joinedload(models.Employee.branch),
        subqueryload(models.Payslip.additions),
        subqueryload(models.Payslip.deductions)
    ).first()

def get_payslips_by_employee(db: Session, employee_id: int):
    """
    Retrieves all payslips for a single employee, ordered by most recent.
    """
    return db.query(models.Payslip).filter(
        models.Payslip.employee_id == employee_id
    ).order_by(models.Payslip.pay_date.desc()).all()
