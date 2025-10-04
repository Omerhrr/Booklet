

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc
from .. import models, schemas
from datetime import date
from .. import crud



def get_next_purchase_bill_number(db: Session, business_id: int) -> str:
    """
    Calculates the next sequential purchase bill number for a given business.
    Example: If the last bill is 'PB-0003', this returns 'PB-0004'.
    """

    last_bill = db.query(models.PurchaseBill.bill_number)\
        .filter(models.PurchaseBill.business_id == business_id)\
        .order_by(desc(models.PurchaseBill.id))\
        .first()

    if not last_bill:

        return "PB-0001"


    last_number_str = last_bill[0].split('-')[-1]
    next_number = int(last_number_str) + 1
    return f"PB-{next_number:04d}"


def get_purchase_bills_by_business(db: Session, business_id: int, branch_id: int, skip: int = 0, limit: int = 100):
    """
    Retrieves all purchase bills for a specific business, ordered by the most recent.
    It also preloads the vendor information to avoid extra database queries.
    """
    return db.query(models.PurchaseBill)\
        .filter(models.PurchaseBill.business_id == business_id,
            models.PurchaseBill.branch_id == branch_id
            )\
        .options(joinedload(models.PurchaseBill.vendor))\
        .order_by(desc(models.PurchaseBill.bill_date), desc(models.PurchaseBill.id))\
        .offset(skip)\
        .limit(limit)\
        .all()
        
def get_purchase_bill(db: Session, bill_id: int, business_id: int):
    """
    Retrieves a single purchase bill by its ID, ensuring it belongs to the correct business.
    It preloads related data (vendor, items, products) to optimize database queries.
    """
    return db.query(models.PurchaseBill).options(
        joinedload(models.PurchaseBill.vendor),
        joinedload(models.PurchaseBill.items).joinedload(models.PurchaseBillItem.product)
    ).filter(
        models.PurchaseBill.id == bill_id,
        models.PurchaseBill.business_id == business_id
    ).first()


def get_purchase_bills_by_vendor(db: Session, vendor_id: int, business_id: int):
    """
    Retrieves all purchase bills for a specific vendor, ordered by date.
    """
    return db.query(models.PurchaseBill)\
        .filter(
            models.PurchaseBill.vendor_id == vendor_id,
            models.PurchaseBill.business_id == business_id
        )\
        .order_by(desc(models.PurchaseBill.bill_date))\
        .all()



def get_next_debit_note_number(db: Session, business_id: int) -> str:
    last_note = db.query(models.DebitNote)\
        .filter(models.DebitNote.business_id == business_id)\
        .order_by(models.DebitNote.id.desc())\
        .first()
    
    if not last_note:
        return "DN-0001"
    
    last_num = int(last_note.debit_note_number.split('-')[1])
    new_num = last_num + 1
    return f"DN-{new_num:04d}"



def get_debit_notes_by_business(db: Session, business_id: int):
    """
    Retrieves all debit notes for a business, ordered by most recent,
    and eagerly loads the related vendor information.
    """
    return db.query(models.DebitNote)\
        .filter(models.DebitNote.business_id == business_id)\
        .options(joinedload(models.DebitNote.vendor))\
        .order_by(desc(models.DebitNote.debit_note_date))\
        .all()



def create_purchase_bill(db: Session, bill_data: schemas.PurchaseBillCreate, business_id: int, branch_id: int):
    """Creates a new purchase bill and the correct, branch-aware ledger entries, including VAT."""
    business = db.query(models.Business).filter(models.Business.id == business_id).first()
    if not business:
        raise ValueError("Business not found.")
        
    vendor = crud.vendor.get_vendor(db, vendor_id=bill_data.vendor_id, business_id=business_id)
    if not vendor:
        raise ValueError("Vendor not found.")

    if vendor.branch_id != branch_id:
        pass

    inventory_account = db.query(models.Account).filter_by(business_id=business_id, name="Inventory").first()
    ap_account = db.query(models.Account).filter_by(business_id=business_id, name="Accounts Payable").first()
    vat_account = db.query(models.Account).filter_by(business_id=business_id, name="VAT Receivable (Input VAT)").first()

    if not ap_account or not inventory_account:
        raise ValueError("Core accounting accounts (Accounts Payable or Inventory) not found.")
    if business.is_vat_registered and not vat_account:
        raise ValueError("VAT Receivable account not found.")

    sub_total = sum(item.quantity * item.price for item in bill_data.items)
    # VAT is now passed from the form
    vat_amount = bill_data.vat_amount if business.is_vat_registered else 0
    total_amount = sub_total + vat_amount

    db_bill = models.PurchaseBill(
        bill_number=get_next_purchase_bill_number(db, business_id=business_id),
        vendor_id=bill_data.vendor_id,
        bill_date=bill_data.bill_date,
        due_date=bill_data.due_date,
        sub_total=sub_total,
        vat_amount=vat_amount,
        total_amount=total_amount,
        branch_id=branch_id,
        business_id=business_id
    )
    db.add(db_bill)
    db.flush()
    for item_data in bill_data.items:
        db.add(models.PurchaseBillItem(
            purchase_bill_id=db_bill.id,
            product_id=item_data.product_id,
            quantity=item_data.quantity,
            price=item_data.price
        ))
        # **THE FIX**: Call the function through the imported crud namespace
        product = crud.inventory.get_product_by_id(db, product_id=item_data.product_id)
        if product:
            product.stock_quantity += item_data.quantity

    # --- UPDATED ACCOUNTING ENTRIES ---
    # 1. Debit Inventory for the NET amount
    db.add(models.LedgerEntry(
        account_id=inventory_account.id, transaction_date=db_bill.bill_date, debit=sub_total,
        description=f"Inventory from Bill #{db_bill.bill_number}",
        vendor_id=bill_data.vendor_id, purchase_bill_id=db_bill.id, branch_id=branch_id
    ))
    # 2. Debit VAT Receivable for the VAT amount
    if business.is_vat_registered and vat_amount > 0:
        db.add(models.LedgerEntry(
            account_id=vat_account.id, transaction_date=db_bill.bill_date, debit=vat_amount,
            description=f"Input VAT on Bill #{db_bill.bill_number}",
            vendor_id=bill_data.vendor_id, purchase_bill_id=db_bill.id, branch_id=branch_id
        ))
    # 3. Credit Accounts Payable for the FULL amount
    db.add(models.LedgerEntry(
        account_id=ap_account.id, transaction_date=db_bill.bill_date, credit=total_amount,
        description=f"Liability for Bill #{db_bill.bill_number}",
        vendor_id=bill_data.vendor_id, purchase_bill_id=db_bill.id, branch_id=branch_id
    ))
    
    return db_bill

def record_payment_for_bill(db: Session, bill: models.PurchaseBill, payment_date: date, amount_paid: float, payment_account_id: int):
    """Records a payment against a purchase bill and creates branch-aware ledger entries."""
    ap_account = db.query(models.Account).filter_by(business_id=bill.business_id, name="Accounts Payable").first()
    if not ap_account:
        raise ValueError("Critical error: Accounts Payable account not found.")

    bill.paid_amount += amount_paid
    if bill.paid_amount >= bill.total_amount - 0.001:
        bill.status = "Paid"
    else:
        bill.status = "Partially Paid"
        
    branch_id = bill.branch_id
    
    db.add(models.LedgerEntry(
        account_id=ap_account.id, transaction_date=payment_date, debit=amount_paid,
        description=f"Payment for Bill #{bill.bill_number}",
        vendor_id=bill.vendor_id, purchase_bill_id=bill.id, branch_id=branch_id
    ))
    db.add(models.LedgerEntry(
        account_id=payment_account_id, transaction_date=payment_date, credit=amount_paid,
        description=f"Payment for Bill #{bill.bill_number}",
        vendor_id=bill.vendor_id, purchase_bill_id=bill.id, branch_id=branch_id
    ))

def create_debit_note_for_bill(db: Session, original_bill: models.PurchaseBill, debit_note_date: date, items_to_return: list):
    """Creates a debit note and its branch-aware ledger entries."""
    if not items_to_return:
        raise ValueError("Cannot create a debit note with no items.")

    total_return_value = sum(item['quantity'] * item['price'] for item in items_to_return)
    
    ap_account = db.query(models.Account).filter_by(business_id=original_bill.business_id, name="Accounts Payable").first()
    inventory_account = db.query(models.Account).filter_by(business_id=original_bill.business_id, name="Inventory").first()
    if not ap_account or not inventory_account:
        raise ValueError("Critical accounting accounts are not configured.")

    branch_id = original_bill.branch_id

    debit_note = models.DebitNote(
        debit_note_number=get_next_debit_note_number(db, business_id=original_bill.business_id),
        vendor_id=original_bill.vendor_id,
        debit_note_date=debit_note_date,
        total_amount=total_return_value,
        reason="Return against bill #" + original_bill.bill_number,
        branch_id=branch_id,
        business_id=original_bill.business_id
    )
    db.add(debit_note)
    db.flush()

    for item_data in items_to_return:
        db.add(models.DebitNoteItem(
            debit_note_id=debit_note.id,
            product_id=item_data['product_id'],
            quantity=item_data['quantity'],
            price=item_data['price']
        ))

        product = crud.inventory.get_product_by_id(db, product_id=item_data['product_id'])
        if product:
            product.stock_quantity -= item_data['quantity']
        db_bill_item = db.query(models.PurchaseBillItem).filter_by(id=item_data['original_item_id']).with_for_update().first()
        if db_bill_item:
            db_bill_item.returned_quantity += item_data['quantity']

    original_bill.total_amount -= total_return_value
    if original_bill.total_amount <= original_bill.paid_amount + 0.001:
        original_bill.status = "Paid"
    elif original_bill.paid_amount > 0:
        original_bill.status = "Partially Paid"
    else:
        original_bill.status = "Unpaid"

    db.add(models.LedgerEntry(
        account_id=ap_account.id, transaction_date=debit_note.debit_note_date, debit=total_return_value,
        description=f"Return on DN #{debit_note.debit_note_number}",
        vendor_id=original_bill.vendor_id, debit_note_id=debit_note.id, branch_id=branch_id
    ))
    db.add(models.LedgerEntry(
        account_id=inventory_account.id, transaction_date=debit_note.debit_note_date, credit=total_return_value,
        description=f"Return on DN #{debit_note.debit_note_number}",
        vendor_id=original_bill.vendor_id, debit_note_id=debit_note.id, branch_id=branch_id
    ))
    
    return debit_note