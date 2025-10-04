from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime, date
from .models import AccountType, PayFrequency

class AccountBase(BaseModel):
    name: str
    type: AccountType

class AccountCreate(AccountBase):
    pass

class AccountUpdate(BaseModel):
    name: str

class Account(AccountBase):
    id: int
    is_system_account: bool
    class Config:
        from_attributes = True

class BankAccountBase(BaseModel):
    account_name: str
    bank_name: Optional[str] = None
    account_number: Optional[str] = None

class BankAccountCreate(BankAccountBase):
    pass

class BankAccount(BankAccountBase):
    id: int
    branch_id: int
    chart_of_account_id: int
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class UserBase(BaseModel):
    username: str
    email: EmailStr

class UserCreate(UserBase):
    password: str

class UserUpdate(UserBase):
    pass

class User(UserBase):
    id: int
    is_superuser: bool
    class Config:
        from_attributes = True

class BranchBase(BaseModel):
    name: str
    currency: str

class BranchCreate(BranchBase):
    pass

class BranchUpdate(BranchBase):
    pass

class Branch(BranchBase):
    id: int
    is_default: bool
    class Config:
        from_attributes = True

class BranchWithDetails(Branch):
    bank_accounts: List[BankAccount] = []

class CustomerBase(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None

class CustomerCreate(CustomerBase):
    branch_id: int
    business_id: int

class CustomerUpdate(CustomerBase):
    pass

class Customer(CustomerBase):
    id: int
    branch_id: int
    business_id: int
    class Config:
        from_attributes = True

class VendorBase(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None

class VendorCreate(VendorBase):
    branch_id: int
    business_id: int

class VendorUpdate(VendorBase):
    pass

class Vendor(VendorBase):
    id: int
    branch_id: int
    business_id: int
    class Config:
        from_attributes = True

class RoleBase(BaseModel):
    name: str
    description: Optional[str] = None

class RoleCreate(RoleBase):
    pass

class Role(RoleBase):
    id: int
    is_system: bool
    class Config:
        from_attributes = True

class CategoryBase(BaseModel):
    name: str
    description: Optional[str] = None

class CategoryCreate(CategoryBase):
    pass

class CategoryUpdate(CategoryBase):
    pass

class Category(CategoryBase):
    id: int
    class Config:
        from_attributes = True

class ProductBase(BaseModel):
    name: str
    sku: Optional[str] = None
    unit: Optional[str] = None
    purchase_price: float
    sales_price: float

class ProductCreate(ProductBase):
    category_id: int
    opening_stock: int

class ProductUpdate(ProductBase):
    category_id: int
    sku: Optional[str] = None

class Product(ProductBase):
    id: int
    category: Category
    opening_stock: int
    stock_quantity: int
    class Config:
        from_attributes = True

class StockAdjustmentCreate(BaseModel):
    quantity_change: int
    reason: str

class StockAdjustment(StockAdjustmentCreate):
    id: int
    product_id: int
    user_id: int
    created_at: datetime
    class Config:
        from_attributes = True

class PurchaseBillItemCreate(BaseModel):
    product_id: int
    quantity: float
    price: float

class PurchaseBillCreate(BaseModel):
    vendor_id: int
    bill_date: date
    due_date: date
    items: List[PurchaseBillItemCreate]
    vat_amount: float = 0.0

class SalesInvoiceItemCreate(BaseModel):
    product_id: int
    quantity: float
    price: float

class SalesInvoiceCreate(BaseModel):
    customer_id: int
    invoice_date: date
    due_date: date
    items: List[SalesInvoiceItemCreate]

class PayrollConfigBase(BaseModel):
    gross_salary: float
    pay_frequency: PayFrequency
    paye_rate: Optional[float] = None
    pension_employee_rate: Optional[float] = None
    pension_employer_rate: Optional[float] = None

class PayrollConfigCreate(PayrollConfigBase):
    pass

class PayrollConfigUpdate(PayrollConfigBase):
    pass

class PayrollConfig(PayrollConfigBase):
    id: int
    employee_id: int
    class Config:
        from_attributes = True

class EmployeeBase(BaseModel):
    full_name: str
    email: EmailStr
    phone_number: Optional[str] = None
    address: Optional[str] = None
    hire_date: date
    is_active: bool = True

class EmployeeCreate(EmployeeBase):
    branch_id: int
    payroll_config: PayrollConfigCreate

class EmployeeUpdate(EmployeeBase):
    pass

class Employee(EmployeeBase):
    id: int
    business_id: int
    branch_id: int
    payroll_config: Optional[PayrollConfig] = None
    class Config:
        from_attributes = True

class PayslipBase(BaseModel):
    pay_period_start: date
    pay_period_end: date
    pay_date: date
    gross_pay: float
    net_pay: float

class PayslipAdditionBase(BaseModel):
    description: str
    amount: float

class PayslipAdditionCreate(PayslipAdditionBase):
    pass

class PayslipAddition(PayslipAdditionBase):
    id: int
    payslip_id: int
    class Config:
        from_attributes = True

class PayslipDeductionBase(BaseModel):
    description: str
    amount: float

class PayslipDeductionCreate(PayslipDeductionBase):
    pass

class PayslipDeduction(PayslipDeductionBase):
    id: int
    payslip_id: int
    class Config:
        from_attributes = True

class Payslip(PayslipBase):
    id: int
    employee_id: int
    additions: List[PayslipAddition] = []
    deductions: List[PayslipDeduction] = []
    class Config:
        from_attributes = True
