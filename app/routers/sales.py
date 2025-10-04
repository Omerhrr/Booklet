
from fastapi import APIRouter, Depends, Request, Form, HTTPException, Query
from starlette.responses import RedirectResponse
from starlette.status import HTTP_303_SEE_OTHER
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from .. import crud, models, schemas, security
from ..database import get_db
from ..templating import templates
import json
from datetime import date
from typing import List, Optional
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import joinedload
from sqlalchemy import desc

router = APIRouter(
    prefix="/sales",
    tags=["Sales"],
    dependencies=[Depends(security.get_current_active_user)]
)

@router.get("/new-invoice", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["sales:create"]))])
async def get_new_sales_invoice_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    # Use the globally selected branch
    active_branch = current_user.selected_branch
    
    # Filter customers and products by the active branch
    customers = crud.get_customers_by_branch(db, branch_id=active_branch.id, business_id=current_user.business_id)
    products_for_json = jsonable_encoder(crud.get_products_by_branch(db, branch_id=active_branch.id))
    user_perms = crud.get_user_permissions(current_user, db)

    return templates.TemplateResponse("sales/create_sales_invoice.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "customers": customers,
        "products": products_for_json,
        "branch_currency": active_branch.currency,
        "today_date": date.today(),
        "title": "Create Sales Invoice"
    })



@router.get("/history", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["sales:view"]))])
async def get_sales_history_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):

    active_branch = current_user.selected_branch
    # Fetch the invoice objects
    invoices_objects = crud.get_sales_invoices_by_business(db, business_id=current_user.business_id, branch_id= active_branch.id)
    
    # **THE KEY STEP**: Convert the objects to a JSON-safe format
    invoices_json = jsonable_encoder(invoices_objects)
    
    user_perms = crud.get_user_permissions(current_user, db)
    
    return templates.TemplateResponse("sales/sales_history.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        # Pass the JSON-safe data to the template
        "invoices_data": invoices_json,
        "title": "Sales History"
    })

@router.get("/new-credit-note", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["sales:create_credit_note"]))])
async def get_new_credit_note_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    customer_id: Optional[int] = Query(None),
    invoice_id: Optional[int] = Query(None)
):
    # Customers and invoices should be filtered by the active branch
    active_branch_id = current_user.selected_branch.id
    customers = crud.get_customers_by_branch(db, branch_id=active_branch_id, business_id=current_user.business_id)
    
    invoices_for_customer = []
    if customer_id:
        invoices_for_customer = db.query(models.SalesInvoice).filter(
            models.SalesInvoice.customer_id == customer_id,
            models.SalesInvoice.branch_id == active_branch_id, # Ensure invoice is from the same branch
            models.SalesInvoice.status != 'Paid' 
        ).all()

    selected_invoice = None
    if invoice_id:
        selected_invoice = crud.get_sales_invoice(db, invoice_id=invoice_id, business_id=current_user.business_id)
        # Security check: ensure the selected invoice belongs to the active branch
        if selected_invoice and selected_invoice.branch_id != active_branch_id:
            raise HTTPException(status_code=403, detail="Invoice does not belong to the active branch.")

    return templates.TemplateResponse("sales/create_credit_note.html", {
        "request": request,
        "user": current_user,
        "user_perms": crud.get_user_permissions(current_user, db),
        "customers": customers,
        "selected_customer_id": customer_id,
        "invoices_for_customer": invoices_for_customer,
        "selected_invoice": selected_invoice,
        "title": "New Credit Note"
    })


@router.get("/credit-notes", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["sales:view"]))])
async def get_credit_notes_history_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
  
    credit_notes_objects = crud.get_credit_notes_by_business(db, business_id=current_user.business_id)
    

    credit_notes_data = jsonable_encoder(credit_notes_objects)
    
    user_perms = crud.get_user_permissions(current_user, db)

    return templates.TemplateResponse("sales/credit_notes_history.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "credit_notes_data": credit_notes_data,
        "title": "Credit Note History"
    })
    
@router.get("/credit-note/{credit_note_id}", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["sales:view"]))])
async def get_credit_note_detail_page(
    credit_note_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):

    credit_note = db.query(models.CreditNote)\
        .options(
            joinedload(models.CreditNote.items).joinedload(models.CreditNoteItem.product),
            joinedload(models.CreditNote.customer)
        )\
        .filter(
            models.CreditNote.id == credit_note_id,
            models.CreditNote.business_id == current_user.business_id
        )\
        .first()

    if not credit_note:
        raise HTTPException(status_code=404, detail="Credit Note not found or not accessible.")

    user_perms = crud.get_user_permissions(current_user, db)

    return templates.TemplateResponse("sales/credit_note_detail.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "credit_note": credit_note,
        "title": f"Credit Note: {credit_note.credit_note_number}"
    })




@router.post("/new-invoice", response_class=RedirectResponse, dependencies=[Depends(security.PermissionChecker(["sales:create"]))])
async def handle_create_sales_invoice(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    customer_id: int = Form(...),
    invoice_date: date = Form(...),
    due_date: date = Form(...),
    items_json: str = Form(...)
):
    try:
        items_list = json.loads(items_json)
        if not items_list:
            raise HTTPException(status_code=400, detail="Cannot create an empty invoice.")

        # Create Pydantic models for the items
        item_schemas = [schemas.SalesInvoiceItemCreate(**item) for item in items_list]
        invoice_schema = schemas.SalesInvoiceCreate(
            customer_id=customer_id,
            invoice_date=invoice_date,
            due_date=due_date,
            items=item_schemas
        )

        # Now, pass the complete and validated schema to the CRUD function.
        crud.create_sales_invoice(
            db=db, 
            invoice_data=invoice_schema, 
            business_id=current_user.business_id, 
            branch_id=current_user.selected_branch.id
        )
        db.commit()
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        print(f"Unexpected error in handle_create_sales_invoice: {e}") # Log for debugging
        raise HTTPException(status_code=500, detail="An unexpected error occurred while creating the sales invoice.")

    return RedirectResponse(url="/sales/history", status_code=HTTP_303_SEE_OTHER)


@router.post("/preview-invoice", response_class=HTMLResponse)
async def handle_preview_sales_invoice(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    customer_id: int = Form(...),
    invoice_date: date = Form(...),
    due_date: date = Form(...),
    items_json: str = Form(...)
):
    customer = crud.get_customer(db, customer_id=customer_id, business_id=current_user.business_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found.")

    items_data = json.loads(items_json)
 
    enriched_items = []
    total_amount = 0
    for item_dict in items_data:
        product = crud.get_product_by_id(db, product_id=item_dict['product_id'])
        if product:
            line_total = item_dict['quantity'] * item_dict['price']
            enriched_items.append({
                "product_name": product.name,
                "quantity": item_dict['quantity'],
                "price": item_dict['price'],
                "line_total": line_total
            })
            total_amount += line_total

    next_invoice_number = crud.get_next_invoice_number(db, business_id=current_user.business_id)
    user_perms = crud.get_user_permissions(current_user, db)

    return templates.TemplateResponse("sales/preview_sales_invoice.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "title": "Preview Sales Invoice",

        "customer_id": customer.id,
        "customer_name": customer.name,
        "invoice_number": next_invoice_number,
        "invoice_date": invoice_date,
        "due_date": due_date,

        "items_for_preview": enriched_items,
        "total_amount": total_amount,

        "items_json_for_save": items_json
    })


@router.post("/record-payment", response_class=RedirectResponse, dependencies=[Depends(security.PermissionChecker(["sales:edit"]))])
async def handle_record_customer_payment(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    invoice_id: int = Form(...),
    customer_id: int = Form(...), 
    payment_date: date = Form(...),
    amount_paid: float = Form(...),
    payment_account_id: int = Form(...) 
):
    invoice = crud.get_sales_invoice(db, invoice_id=invoice_id, business_id=current_user.business_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Sales invoice not found.")

    # Security check: Ensure the invoice belongs to the user's active branch
    if invoice.branch_id != current_user.selected_branch.id:
        raise HTTPException(status_code=403, detail="You can only record payments for invoices in your active branch.")

    try:
        crud.sales.record_payment_for_invoice(
            db=db,
            invoice=invoice,
            payment_date=payment_date,
            amount_paid=amount_paid,
            payment_account_id=payment_account_id
        )
        db.commit()
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        print(f"Unexpected error in handle_record_customer_payment: {e}") # For server-side debugging
        raise HTTPException(status_code=500, detail="An unexpected error occurred while recording the payment.")

    # Redirect back to the customer's detail page, on the ledger tab for confirmation.
    return RedirectResponse(url=f"/crm/customers/{customer_id}/view?tab=ledger", status_code=HTTP_303_SEE_OTHER)








@router.post("/new-credit-note", response_class=RedirectResponse, dependencies=[Depends(security.PermissionChecker(["purchases:create_debit_note"]))])
async def handle_create_credit_note(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    original_invoice_id: int = Form(...),
    credit_note_date: date = Form(...),
    product_id: list[int] = Form(...),
    price: list[float] = Form(...),
    return_quantity: list[float] = Form(...)
):
    original_invoice = crud.get_sales_invoice(db, invoice_id=original_invoice_id, business_id=current_user.business_id)
    if not original_invoice:
        raise HTTPException(status_code=404, detail="Original sales invoice not found.")
    if original_invoice.branch_id != current_user.selected_branch.id:
        raise HTTPException(status_code=403, detail="You can only create credit notes for invoice in your active branch.")

    items_to_return = []
    for i in range(len(product_id)):
        if float(return_quantity[i]) > 0:
            original_item = next((item for item in original_invoice.items if item.product_id == int(product_id[i])), None)
            if not original_item:
                raise HTTPException(status_code=400, detail=f"Invalid product ID {product_id[i]} in form.")
            max_returnable = original_item.quantity - original_item.returned_quantity
            if float(return_quantity[i]) > max_returnable:
                raise HTTPException(status_code=400, detail=f"Cannot return more than {max_returnable} for '{original_item.product.name}'.")
            items_to_return.append({
                "product_id": int(product_id[i]),
                "quantity": float(return_quantity[i]),
                "price": float(price[i]),
                "original_item_id": original_item.id  
            })
    
    try:
        crud.create_credit_note_for_invoice(
            db=db,
            original_invoice=original_invoice,
            credit_note_date=credit_note_date,
            items_to_return=items_to_return
        )
        db.commit()
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"A server error occurred: {str(e)}")

    return RedirectResponse(url=f"/crm/customers/{original_invoice.customer_id}/view?tab=invoices", status_code=HTTP_303_SEE_OTHER)

@router.get("/{invoice_id}", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["sales:view"]))])
async def get_sales_invoice_detail_page(
    request: Request,
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    invoice = crud.get_sales_invoice(db, invoice_id=invoice_id, business_id=current_user.business_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Sales invoice not found or not accessible.")
        
    user_perms = crud.get_user_permissions(current_user, db)
    
    return templates.TemplateResponse("sales/sales_invoice_detail.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "invoice": invoice,
        "title": f"Sales Invoice {invoice.invoice_number}"
    })
