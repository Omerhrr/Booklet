# app/crud/sales.py
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from .. import models, schemas, crud  
from datetime import date

def get_next_invoice_number(db: Session, business_id: int) -> str:
    """Calculates the next sequential sales invoice number."""
    last_invoice = db.query(models.SalesInvoice.invoice_number)\
        .filter(models.SalesInvoice.business_id == business_id)\
        .order_by(desc(models.SalesInvoice.id))\
        .first()
    if not last_invoice:
        return "INV-0001"
    last_number = int(last_invoice[0].split('-')[-1])
    return f"INV-{last_number + 1:04d}"

def get_sales_invoices_by_business(db: Session, business_id: int, branch_id: int, skip: int = 0, limit: int = 100):
    """Retrieves all sales invoices for a specific branch."""
    return db.query(models.SalesInvoice)\
        .filter(
            models.SalesInvoice.business_id == business_id,
            models.SalesInvoice.branch_id == branch_id
        )\
        .options(joinedload(models.SalesInvoice.customer))\
        .order_by(desc(models.SalesInvoice.invoice_date), desc(models.SalesInvoice.id))\
        .offset(skip)\
        .limit(limit)\
        .all()

def get_sales_invoice(db: Session, invoice_id: int, business_id: int):
    """Retrieves a single sales invoice with all its details."""
    return db.query(models.SalesInvoice).options(
        joinedload(models.SalesInvoice.customer),
        joinedload(models.SalesInvoice.items).joinedload(models.SalesInvoiceItem.product)
    ).filter(
        models.SalesInvoice.id == invoice_id,
        models.SalesInvoice.business_id == business_id
    ).first()

def get_sales_invoices_by_customer(db: Session, customer_id: int, business_id: int):
    """Retrieves all sales invoices for a specific customer."""
    return db.query(models.SalesInvoice)\
        .filter(
            models.SalesInvoice.customer_id == customer_id,
            models.SalesInvoice.business_id == business_id
        )\
        .order_by(desc(models.SalesInvoice.invoice_date))\
        .all()

def create_sales_invoice(db: Session, invoice_data: schemas.SalesInvoiceCreate, business_id: int, branch_id: int):
    """Creates a new sales invoice and the correct, branch-aware ledger entries, including VAT if applicable."""
    business = db.query(models.Business).filter(models.Business.id == business_id).first()
    if not business:
        raise ValueError("Business not found.")

    customer = crud.customer.get_customer(db, customer_id=invoice_data.customer_id, business_id=business_id)
    if not customer:
        raise ValueError("Customer not found.")
    if customer.branch_id != branch_id:
        raise ValueError(f"Customer '{customer.name}' does not belong to the selected branch.")

    # Fetch all necessary accounts
    ar_account = db.query(models.Account).filter_by(business_id=business_id, name="Accounts Receivable").first()
    revenue_account = db.query(models.Account).filter_by(business_id=business_id, name="Sales Revenue").first()
    cogs_account = db.query(models.Account).filter_by(business_id=business_id, name="Cost of Goods Sold").first()
    inventory_account = db.query(models.Account).filter_by(business_id=business_id, name="Inventory").first()
    vat_account = db.query(models.Account).filter_by(business_id=business_id, name="VAT Payable (Output VAT)").first()

    if not all([ar_account, revenue_account, cogs_account, inventory_account]):
        raise ValueError("Core accounting accounts (AR, Revenue, COGS, Inventory) not found.")
    if business.is_vat_registered and not vat_account:
        raise ValueError("VAT Payable account not found. Please check Chart of Accounts.")

    # Calculate totals
    sub_total = sum(item.quantity * item.price for item in invoice_data.items)
    vat_amount = 0
    if business.is_vat_registered:
        vat_amount = sub_total * business.vat_rate

    total_amount = sub_total + vat_amount
    total_cost = 0
    for item_data in invoice_data.items:
        product = crud.inventory.get_product_by_id(db, product_id=item_data.product_id)
        if not product or product.branch_id != branch_id:
            raise ValueError(f"Product with ID {item_data.product_id} not found in this branch.")
        if product.stock_quantity < item_data.quantity:
            raise ValueError(f"Insufficient stock for '{product.name}'. Available: {product.stock_quantity}, Requested: {item_data.quantity}.")
        total_cost += product.purchase_price * item_data.quantity

    db_invoice = models.SalesInvoice(
        invoice_number=get_next_invoice_number(db, business_id=business_id),
        customer_id=customer.id,
        invoice_date=invoice_data.invoice_date,
        due_date=invoice_data.due_date,
        sub_total=sub_total,
        vat_amount=vat_amount,
        total_amount=total_amount,
        branch_id=branch_id,
        business_id=business_id
    )
    db.add(db_invoice)
    db.flush()

    for item_data in invoice_data.items:
        db.add(models.SalesInvoiceItem(
            sales_invoice_id=db_invoice.id,
            product_id=item_data.product_id,
            quantity=item_data.quantity,
            price=item_data.price
        ))
        product = db.query(models.Product).filter(models.Product.id == item_data.product_id).with_for_update().first()
        if product:
            product.stock_quantity -= item_data.quantity

    # --- UPDATED ACCOUNTING ENTRIES ---
    desc = f"Sale on Invoice #{db_invoice.invoice_number}"
    # 1. Debit Accounts Receivable for the FULL amount
    db.add(models.LedgerEntry(account_id=ar_account.id, transaction_date=db_invoice.invoice_date, debit=total_amount, description=desc, customer_id=customer.id, sales_invoice_id=db_invoice.id, branch_id=branch_id))
    # 2. Credit Sales Revenue for the NET amount
    db.add(models.LedgerEntry(account_id=revenue_account.id, transaction_date=db_invoice.invoice_date, credit=sub_total, description=desc, customer_id=customer.id, sales_invoice_id=db_invoice.id, branch_id=branch_id))
    # 3. Credit VAT Payable for the VAT amount
    if business.is_vat_registered and vat_amount > 0:
        db.add(models.LedgerEntry(account_id=vat_account.id, transaction_date=db_invoice.invoice_date, credit=vat_amount, description=desc, customer_id=customer.id, sales_invoice_id=db_invoice.id, branch_id=branch_id))
    
    # COGS entries remain the same
    cogs_desc = f"COGS for Invoice #{db_invoice.invoice_number}"
    db.add(models.LedgerEntry(account_id=cogs_account.id, transaction_date=db_invoice.invoice_date, debit=total_cost, description=cogs_desc, customer_id=customer.id, sales_invoice_id=db_invoice.id, branch_id=branch_id))
    db.add(models.LedgerEntry(account_id=inventory_account.id, transaction_date=db_invoice.invoice_date, credit=total_cost, description=cogs_desc, customer_id=customer.id, sales_invoice_id=db_invoice.id, branch_id=branch_id))
    
    return db_invoice
def record_payment_for_invoice(db: Session, invoice: models.SalesInvoice, payment_date: date, amount_paid: float, payment_account_id: int):
    """Records a payment against a sales invoice and creates branch-aware ledger entries."""
    ar_account = db.query(models.Account).filter_by(business_id=invoice.business_id, name="Accounts Receivable").first()
    if not ar_account:
        raise ValueError("Critical error: Accounts Receivable account not found.")

    invoice.paid_amount += amount_paid
    if invoice.paid_amount >= invoice.total_amount - 0.001:
        invoice.status = "Paid"
    else:
        invoice.status = "Partially Paid"
    
    branch_id = invoice.branch_id

    db.add(models.LedgerEntry(
        account_id=ar_account.id, 
        transaction_date=payment_date, 
        credit=amount_paid,
        description=f"Payment for Invoice #{invoice.invoice_number}",
        customer_id=invoice.customer_id, 
        sales_invoice_id=invoice.id,
        branch_id=branch_id
    ))
    db.add(models.LedgerEntry(
        account_id=payment_account_id, 
        transaction_date=payment_date, 
        debit=amount_paid,
        description=f"Payment received for Invoice #{invoice.invoice_number}",
        customer_id=invoice.customer_id, 
        sales_invoice_id=invoice.id,
        branch_id=branch_id
    ))

def create_credit_note_for_invoice(db: Session, original_invoice: models.SalesInvoice, credit_note_date: date, items_to_return: list):
    """Creates a credit note for a sales return and its branch-aware ledger entries."""
    if not items_to_return:
        raise ValueError("Cannot create a credit note with no items.")

    business_id = original_invoice.business_id
    branch_id = original_invoice.branch_id

    ar_account = db.query(models.Account).filter_by(business_id=business_id, name="Accounts Receivable").first()
    revenue_account = db.query(models.Account).filter_by(business_id=business_id, name="Sales Revenue").first()
    cogs_account = db.query(models.Account).filter_by(business_id=business_id, name="Cost of Goods Sold").first()
    inventory_account = db.query(models.Account).filter_by(business_id=business_id, name="Inventory").first()
    if not all([ar_account, revenue_account, cogs_account, inventory_account]):
        raise ValueError("Core accounting accounts not found.")

    total_return_value = sum(item['quantity'] * item['price'] for item in items_to_return)
    total_return_cost = sum(item['quantity'] * crud.inventory.get_product_by_id(db, item['product_id']).purchase_price for item in items_to_return)

    credit_note = models.CreditNote(
        credit_note_number=get_next_credit_note_number(db, business_id=business_id),
        customer_id=original_invoice.customer_id,
        credit_note_date=credit_note_date,
        total_amount=total_return_value,
        reason="Return against invoice #" + original_invoice.invoice_number,
        branch_id=branch_id,
        business_id=business_id
    )
    db.add(credit_note)
    db.flush()

    for item in items_to_return:
        db.add(models.CreditNoteItem(credit_note_id=credit_note.id, product_id=item['product_id'], quantity=item['quantity'], price=item['price']))
        product = crud.inventory.get_product_by_id(db, product_id=item['product_id'])
        if product:
            product.stock_quantity += item['quantity']
        db_item = db.query(models.SalesInvoiceItem).filter_by(id=item['original_item_id']).first()
        if db_item:
            db_item.returned_quantity += item['quantity']

    original_invoice.total_amount -= total_return_value
    if original_invoice.total_amount <= original_invoice.paid_amount + 0.001:
        original_invoice.status = "Paid"

    db.add(models.LedgerEntry(account_id=ar_account.id, transaction_date=credit_note.credit_note_date, credit=total_return_value, description=f"Return on CN #{credit_note.credit_note_number}", customer_id=credit_note.customer_id, credit_note_id=credit_note.id, branch_id=branch_id))
    db.add(models.LedgerEntry(account_id=revenue_account.id, transaction_date=credit_note.credit_note_date, debit=total_return_value, description=f"Return on CN #{credit_note.credit_note_number}", customer_id=credit_note.customer_id, credit_note_id=credit_note.id, branch_id=branch_id))
    db.add(models.LedgerEntry(account_id=inventory_account.id, transaction_date=credit_note.credit_note_date, debit=total_return_cost, description=f"Inventory return on CN #{credit_note.credit_note_number}", customer_id=credit_note.customer_id, credit_note_id=credit_note.id, branch_id=branch_id))
    db.add(models.LedgerEntry(account_id=cogs_account.id, transaction_date=credit_note.credit_note_date, credit=total_return_cost, description=f"COGS reversal on CN #{credit_note.credit_note_number}", customer_id=credit_note.customer_id, credit_note_id=credit_note.id, branch_id=branch_id))

    return credit_note

def get_next_credit_note_number(db: Session, business_id: int) -> str:
    """Calculates the next sequential credit note number."""
    last_note = db.query(models.CreditNote)\
        .filter(models.CreditNote.business_id == business_id)\
        .order_by(models.CreditNote.id.desc())\
        .first()
    if not last_note:
        return "CN-0001"
    last_num = int(last_note.credit_note_number.split('-')[1])
    return f"CN-{last_num + 1:04d}"

def get_credit_notes_by_business(db: Session, business_id: int, branch_id: int):
    """
    Retrieves all credit notes for a specific branch, ordered by most recent.
    """
    return db.query(models.CreditNote)\
        .filter(
            models.CreditNote.business_id == business_id,
            models.CreditNote.branch_id == branch_id
        )\
        .options(joinedload(models.CreditNote.customer))\
        .order_by(desc(models.CreditNote.credit_note_date))\
        .all()
