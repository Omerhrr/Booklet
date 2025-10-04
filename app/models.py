# app/models.py
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, DateTime, func, Float, Text, UniqueConstraint, Date
from sqlalchemy.orm import relationship
from .database import Base
from sqlalchemy import Enum as SQLAlchemyEnum
import enum
from typing import ClassVar, Union

class AccountType(str, enum.Enum):
    ASSET = "Asset"
    LIABILITY = "Liability"
    EQUITY = "Equity"
    REVENUE = "Revenue"
    EXPENSE = "Expense"

class Business(Base):
    __tablename__ = "businesses"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, index=True)
    plan = Column(String, default="basic")

    is_vat_registered = Column(Boolean, default=False)
    vat_rate = Column(Float, default=0.0)
    
    users = relationship("User", back_populates="business")
    branches = relationship("Branch", back_populates="business")
    roles = relationship("Role", back_populates="business")
    categories = relationship("Category", back_populates="business")
    accounts = relationship("Account", back_populates="business")
    ai_provider = Column(String, nullable=True) 
    encrypted_api_key = Column(String, nullable=True) 
    users = relationship("User", back_populates="business")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_superuser = Column(Boolean, default=False)
    business_id = Column(Integer, ForeignKey("businesses.id"))
    business = relationship("Business", back_populates="users")
    roles = relationship("UserBranchRole", back_populates="user")

    selected_branch: ClassVar[Union["Branch", None]] = None
    accessible_branches: ClassVar[list["Branch"]] = []

class Branch(Base):
    __tablename__ = "branches"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    currency = Column(String, default="USD")
    is_default = Column(Boolean, default=False)
    business_id = Column(Integer, ForeignKey("businesses.id"))
    business = relationship("Business", back_populates="branches")
    customers = relationship("Customer", back_populates="branch")
    vendors = relationship("Vendor", back_populates="branch")
    products = relationship("Product", back_populates="branch")
    user_roles = relationship("UserBranchRole", back_populates="branch")
    budgets = relationship("Budget", back_populates="branch")
    bank_accounts = relationship("BankAccount", back_populates="branch", cascade="all, delete-orphan")
    

    __table_args__ = (
        UniqueConstraint('business_id', 'name', name='_business_branch_name_uc'),
    )


class Account(Base):
    __tablename__ = "accounts"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    type = Column(SQLAlchemyEnum(AccountType), nullable=False)
    description = Column(String, nullable=True) 
    is_system_account = Column(Boolean, default=False)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    business = relationship("Business", back_populates="accounts")
    ledger_entries = relationship("LedgerEntry", back_populates="account")
    budget_lines = relationship("BudgetLine", back_populates="account")

    bank_account_details = relationship("BankAccount", back_populates="chart_of_account", uselist=False, cascade="all, delete-orphan")



class DebitNote(Base):
    __tablename__ = "debit_notes"
    id = Column(Integer, primary_key=True)
    debit_note_number = Column(String,  nullable=False)
    vendor_id = Column(Integer, ForeignKey("vendors.id"), nullable=False)
    vendor = relationship("Vendor")
    debit_note_date = Column(Date, nullable=False)
    total_amount = Column(Float, default=0.0)
    reason = Column(String, nullable=True)
    
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False)
    
    items = relationship("DebitNoteItem", back_populates="debit_note", cascade="all, delete-orphan")

class DebitNoteItem(Base):
    __tablename__ = "debit_note_items"
    id = Column(Integer, primary_key=True)
    debit_note_id = Column(Integer, ForeignKey("debit_notes.id"), nullable=False)
    debit_note = relationship("DebitNote", back_populates="items")
    
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    product = relationship("Product")
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)

class JournalVoucher(Base):
    __tablename__ = "journal_vouchers"
    id = Column(Integer, primary_key=True)
    voucher_number = Column(String, nullable=False)
    transaction_date = Column(Date, nullable=False)
    description = Column(Text, nullable=True)
    
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False)
    
    business = relationship("Business")
    branch = relationship("Branch")
    
    ledger_entries = relationship("LedgerEntry", back_populates="journal_voucher")

class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    id = Column(Integer, primary_key=True)
    transaction_date = Column(Date, nullable=False)
    description = Column(String)
    debit = Column(Float, default=0.0)
    credit = Column(Float, default=0.0)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    account = relationship("Account", back_populates="ledger_entries")

    vendor_id = Column(Integer, ForeignKey("vendors.id"), nullable=True)
    vendor = relationship("Vendor")
    
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    customer = relationship("Customer")

    purchase_bill_id = Column(Integer, ForeignKey("purchase_bills.id"), nullable=True)
    purchase_bill = relationship("PurchaseBill")

    debit_note_id = Column(Integer, ForeignKey("debit_notes.id"), nullable=True)
    debit_note = relationship("DebitNote")

    sales_invoice_id = Column(Integer, ForeignKey("sales_invoices.id"), nullable=True)
    sales_invoice = relationship("SalesInvoice")
    credit_note_id = Column(Integer, ForeignKey("credit_notes.id"), nullable=True)
    credit_note = relationship("CreditNote")


    
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False)
    branch = relationship("Branch")

    journal_voucher_id = Column(Integer, ForeignKey("journal_vouchers.id"), nullable=True)
    journal_voucher = relationship("JournalVoucher", back_populates="ledger_entries")


    other_income_id = Column(Integer, ForeignKey("other_incomes.id"), nullable=True)
    other_income = relationship("OtherIncome", back_populates="ledger_entries")
    
    # NEW: Link to FundTransfer
    fund_transfer_id = Column(Integer, ForeignKey("fund_transfers.id"), nullable=True)
    fund_transfer = relationship("FundTransfer", back_populates="ledger_entries")

    is_reconciled = Column(Boolean, default=False, nullable=False)
    reconciliation_id = Column(Integer, ForeignKey("bank_reconciliations.id"), nullable=True)
    reconciliation = relationship("BankReconciliation", back_populates="ledger_entries")



class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    email = Column(String)
    phone = Column(String)
    address = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    branch_id = Column(Integer, ForeignKey("branches.id"))
    branch = relationship("Branch", back_populates="customers")

    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    business = relationship("Business")

    sales_invoices = relationship("SalesInvoice", back_populates="customer")
    credit_notes = relationship("CreditNote", back_populates="customer")


class Vendor(Base):
    __tablename__ = "vendors"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    email = Column(String)
    phone = Column(String)
    address = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    branch_id = Column(Integer, ForeignKey("branches.id"))
    branch = relationship("Branch", back_populates="vendors")

    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    business = relationship("Business")

class Role(Base):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    description = Column(String, nullable=True)
    is_system = Column(Boolean, default=False)
    business_id = Column(Integer, ForeignKey("businesses.id"))
    business = relationship("Business", back_populates="roles")
    permissions = relationship("RolePermission", back_populates="role", cascade="all, delete-orphan")
    users = relationship("UserBranchRole", back_populates="role")

class Permission(Base):
    __tablename__ = "permissions"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    category = Column(String)

class RolePermission(Base):
    __tablename__ = "role_permissions"
    role_id = Column(Integer, ForeignKey("roles.id"), primary_key=True)
    permission_id = Column(Integer, ForeignKey("permissions.id"), primary_key=True)
    role = relationship("Role", back_populates="permissions")
    permission = relationship("Permission")

class UserBranchRole(Base):
    __tablename__ = "user_branch_roles"
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), primary_key=True)
    role_id = Column(Integer, ForeignKey("roles.id"), primary_key=True)
    user = relationship("User", back_populates="roles")
    role = relationship("Role", back_populates="users")
    branch = relationship("Branch", back_populates="user_roles")

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    description = Column(String, nullable=True)
    

    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False)
    business_id = Column(Integer, ForeignKey("businesses.id"))

    branch = relationship("Branch") 
    business = relationship("Business", back_populates="categories")
    products = relationship("Product", back_populates="category")

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    sku = Column(String, nullable=True, index=True)
    unit = Column(String, nullable=True)
    purchase_price = Column(Float)
    sales_price = Column(Float)
    opening_stock = Column(Integer, default=0)
    stock_quantity = Column(Integer, default=0)

    branch_id = Column(Integer, ForeignKey("branches.id"))
    branch = relationship("Branch", back_populates="products")
    category_id = Column(Integer, ForeignKey("categories.id"))
    category = relationship("Category", back_populates="products")
    stock_adjustments = relationship("StockAdjustment", back_populates="product")

class StockAdjustment(Base):
    __tablename__ = "stock_adjustments"
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    product = relationship("Product", back_populates="stock_adjustments")
    quantity_change = Column(Integer)
    reason = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("User")

class PurchaseBill(Base):
    __tablename__ = "purchase_bills"
    id = Column(Integer, primary_key=True)
    bill_date = Column(Date, nullable=False)
    bill_number = Column(String, nullable=False)
    due_date = Column(Date)
    sub_total = Column(Float, nullable=False, default=0.0)
    vat_amount = Column(Float, nullable=False, default=0.0)
    total_amount = Column(Float, nullable=False)
    paid_amount = Column(Float, nullable=False, default=0.0)
    status = Column(String, nullable=False, default="Unpaid")
    
    vendor_id = Column(Integer, ForeignKey("vendors.id"), nullable=False)
    vendor = relationship("Vendor")
    
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False)
    branch = relationship("Branch")
    
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    business = relationship("Business")
    
    items = relationship("PurchaseBillItem", back_populates="purchase_bill", cascade="all, delete-orphan")
    __table_args__ = (
        UniqueConstraint('business_id', 'bill_number', name='_business_bill_number_uc'),
    )

class PurchaseBillItem(Base):
    __tablename__ = "purchase_bill_items"
    id = Column(Integer, primary_key=True)
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    
    purchase_bill_id = Column(Integer, ForeignKey("purchase_bills.id"), nullable=False)
    purchase_bill = relationship("PurchaseBill", back_populates="items")
    
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    product = relationship("Product")
    returned_quantity = Column(Float, default=0.0)

class SalesInvoice(Base):
    __tablename__ = "sales_invoices"
    id = Column(Integer, primary_key=True)
    invoice_date = Column(Date, nullable=False)
    invoice_number = Column(String, nullable=False)
    due_date = Column(Date)
    sub_total = Column(Float, nullable=False, default=0.0)
    vat_amount = Column(Float, nullable=False, default=0.0)
    total_amount = Column(Float, nullable=False)
    paid_amount = Column(Float, nullable=False, default=0.0)
    status = Column(String, nullable=False, default="Unpaid")



    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    customer = relationship("Customer", back_populates="sales_invoices")
    
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False)
    branch = relationship("Branch")
    
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    business = relationship("Business")
    
    items = relationship("SalesInvoiceItem", back_populates="sales_invoice", cascade="all, delete-orphan")
    
    __table_args__ = (
        UniqueConstraint('business_id', 'invoice_number', name='_business_invoice_number_uc'),
    )

class SalesInvoiceItem(Base):
    __tablename__ = "sales_invoice_items"
    id = Column(Integer, primary_key=True)
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    
    sales_invoice_id = Column(Integer, ForeignKey("sales_invoices.id"), nullable=False)
    sales_invoice = relationship("SalesInvoice", back_populates="items")
    
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    product = relationship("Product")
    
    returned_quantity = Column(Float, default=0.0)

class CreditNote(Base):
    __tablename__ = "credit_notes"
    id = Column(Integer, primary_key=True)
    credit_note_number = Column(String,  nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    customer = relationship("Customer", back_populates="credit_notes")
    credit_note_date = Column(Date, nullable=False)
    total_amount = Column(Float, default=0.0)
    reason = Column(String, nullable=True)
    
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False)
    
    items = relationship("CreditNoteItem", back_populates="credit_note", cascade="all, delete-orphan")

class CreditNoteItem(Base):
    __tablename__ = "credit_note_items"
    id = Column(Integer, primary_key=True)
    credit_note_id = Column(Integer, ForeignKey("credit_notes.id"), nullable=False)
    credit_note = relationship("CreditNote", back_populates="items")
    
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    product = relationship("Product")
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)

class Expense(Base):
    __tablename__ = "expenses"
    id = Column(Integer, primary_key=True)
    expense_date = Column(Date, nullable=False)
    category = Column(String, nullable=False)
    sub_total = Column(Float, nullable=False, default=0.0)
    vat_amount = Column(Float, nullable=False, default=0.0)
    amount = Column(Float, nullable=False)
    description = Column(Text, nullable=True)
    expense_number = Column(String, nullable=False)
    
    paid_from_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    paid_from_account = relationship("Account", foreign_keys=[paid_from_account_id])

    expense_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    expense_account = relationship("Account", foreign_keys=[expense_account_id])

    vendor_id = Column(Integer, ForeignKey("vendors.id"), nullable=True)
    vendor = relationship("Vendor")

    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False)
    branch = relationship("Branch")
    
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    business = relationship("Business")

    __table_args__ = (
        UniqueConstraint('business_id', 'expense_number', name='_business_expense_number_uc'),
    )

class PayFrequency(str, enum.Enum):
    MONTHLY = "Monthly"
    WEEKLY = "Weekly"
    BI_WEEKLY = "Bi-Weekly"

class Employee(Base):
    __tablename__ = "employees"
    id = Column(Integer, primary_key=True)
    full_name = Column(String, nullable=False)
    email = Column(String, nullable=False, index=True)
    phone_number = Column(String, nullable=True)
    address = Column(Text, nullable=True)
    hire_date = Column(Date, nullable=False)
    is_active = Column(Boolean, default=True)
    termination_date = Column(Date, nullable=True)

    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    business = relationship("Business")
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False)
    branch = relationship("Branch")

    payroll_config = relationship("PayrollConfig", back_populates="employee", uselist=False, cascade="all, delete-orphan")
    payslips = relationship("Payslip", back_populates="employee", cascade="all, delete-orphan")

class PayrollConfig(Base):
    __tablename__ = "payroll_configs"
    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, unique=True)
    gross_salary = Column(Float, nullable=False)
    pay_frequency = Column(SQLAlchemyEnum(PayFrequency), nullable=False)
    
    paye_rate = Column(Float, nullable=True)
    pension_employee_rate = Column(Float, nullable=True)
    pension_employer_rate = Column(Float, nullable=True)

    employee = relationship("Employee", back_populates="payroll_config")

class Payslip(Base):
    __tablename__ = "payslips"
    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    
    pay_period_start = Column(Date, nullable=False)
    pay_period_end = Column(Date, nullable=False)
    pay_date = Column(Date, nullable=False)

    gross_pay = Column(Float, nullable=False)
    paye_deduction = Column(Float, default=0.0)
    pension_employee_deduction = Column(Float, default=0.0)
    pension_employer_contribution = Column(Float, default=0.0)
    total_deductions = Column(Float, default=0.0)
    net_pay = Column(Float, nullable=False)
    ledger_entries = relationship("LedgerEntry", back_populates="payslip")
    additions = relationship("PayslipAddition", back_populates="payslip", cascade="all, delete-orphan")
    deductions = relationship("PayslipDeduction", back_populates="payslip", cascade="all, delete-orphan")
    employee = relationship("Employee", back_populates="payslips")

class PayslipAddition(Base):
    __tablename__ = "payslip_additions"
    id = Column(Integer, primary_key=True)
    payslip_id = Column(Integer, ForeignKey("payslips.id"), nullable=False)
    description = Column(String, nullable=False)
    amount = Column(Float, nullable=False)

    payslip = relationship("Payslip", back_populates="additions")

class PayslipDeduction(Base):
    __tablename__ = "payslip_deductions"
    id = Column(Integer, primary_key=True)
    payslip_id = Column(Integer, ForeignKey("payslips.id"), nullable=False)
    description = Column(String, nullable=False)
    amount = Column(Float, nullable=False)

    payslip = relationship("Payslip", back_populates="deductions")

LedgerEntry.payslip_id = Column(Integer, ForeignKey("payslips.id"), nullable=True)
LedgerEntry.payslip = relationship("Payslip", back_populates="ledger_entries")

class Budget(Base):
    __tablename__ = "budgets"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False)
    branch = relationship("Branch", back_populates="budgets")
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    lines = relationship("BudgetLine", back_populates="budget", cascade="all, delete-orphan")
    
    __table_args__ = (
        UniqueConstraint('branch_id', 'name', name='_branch_budget_name_uc'),
    )

class BudgetLine(Base):
    __tablename__ = "budget_lines"
    id = Column(Integer, primary_key=True)
    budget_id = Column(Integer, ForeignKey("budgets.id"), nullable=False)
    budget = relationship("Budget", back_populates="lines")
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    account = relationship("Account", back_populates="budget_lines")
    amount = Column(Float, nullable=False, default=0.0)



class OtherIncome(Base):
    __tablename__ = "other_incomes"
    id = Column(Integer, primary_key=True)
    income_date = Column(Date, nullable=False)
    income_number = Column(String, nullable=False, unique=True)
    description = Column(Text, nullable=True)
    amount = Column(Float, nullable=False)

    # The Revenue account this income is for (e.g., "Interest Income")
    income_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    income_account = relationship("Account", foreign_keys=[income_account_id])

    # The Asset account the money was deposited INTO (e.g., "Bank")
    deposited_to_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    deposited_to_account = relationship("Account", foreign_keys=[deposited_to_account_id])

    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False)
    branch = relationship("Branch")
    
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    business = relationship("Business")
    
    ledger_entries = relationship("LedgerEntry", back_populates="other_income")


class FundTransfer(Base):
    __tablename__ = "fund_transfers"
    id = Column(Integer, primary_key=True)
    transfer_date = Column(Date, nullable=False)
    description = Column(Text, nullable=True)
    amount = Column(Float, nullable=False)

    # The Asset account the money is coming FROM
    from_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    from_account = relationship("Account", foreign_keys=[from_account_id])

    # The Asset account the money is going TO
    to_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    to_account = relationship("Account", foreign_keys=[to_account_id])

    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False)
    branch = relationship("Branch")
    
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    business = relationship("Business")
    
    ledger_entries = relationship("LedgerEntry", back_populates="fund_transfer")


class BankReconciliation(Base):
    __tablename__ = "bank_reconciliations"
    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    statement_date = Column(Date, nullable=False)
    statement_balance = Column(Float, nullable=False)
    reconciled_at = Column(DateTime(timezone=True), server_default=func.now())
    
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False)
    
    account = relationship("Account")
    ledger_entries = relationship("LedgerEntry", back_populates="reconciliation")


class BankAccount(Base):
    __tablename__ = "bank_accounts"
    id = Column(Integer, primary_key=True)
    account_name = Column(String, nullable=False)
    bank_name = Column(String, nullable=True)
    account_number = Column(String, nullable=True, index=True)
    
    # This is the link to the corresponding entry in the main 'accounts' table
    chart_of_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False, unique=True)
    chart_of_account = relationship("Account", back_populates="bank_account_details")

    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False)
    branch = relationship("Branch", back_populates="bank_accounts")
    
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    business = relationship("Business")

    last_reconciliation_date = Column(Date, nullable=True)
    last_reconciliation_balance = Column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint('branch_id', 'account_name', name='_branch_bank_account_name_uc'),
    )

