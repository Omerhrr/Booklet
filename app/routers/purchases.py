
from fastapi import APIRouter, Depends, Request, Form, HTTPException, Response, Query

from starlette.responses import RedirectResponse
from starlette.status import HTTP_303_SEE_OTHER

from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from .. import crud, models, schemas, security
from ..database import get_db
from ..templating import templates
import json
from datetime import datetime, date
from fastapi.encoders import jsonable_encoder 
from typing import List, Optional
from .. import crud
router = APIRouter(
    prefix="/purchases",
    tags=["Purchases"],
    dependencies=[Depends(security.get_current_active_user)]
)


@router.get("/new-bill", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["purchases:create"]))])
async def get_new_purchase_bill_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    active_branch = current_user.selected_branch

    # Filter vendors and products by the active branch
    vendors = crud.get_vendors_by_branch(db, branch_id=active_branch.id, business_id=current_user.business_id)
    products_for_json = jsonable_encoder(crud.get_products_by_branch(db, branch_id=active_branch.id))
    user_perms = crud.get_user_permissions(current_user, db)

    return templates.TemplateResponse("purchases/create_purchase_bill.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "vendors": vendors,
        "products": products_for_json,
        "branch_currency": active_branch.currency,
        "today_date": date.today(), 
        "title": "Create Purchase Bill"
    })


@router.get("/new-debit-note", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["purchases:create_debit_note"]))])
async def get_new_debit_note_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    vendor_id: Optional[int] = Query(None),
    bill_id: Optional[int] = Query(None)
):
    active_branch_id = current_user.selected_branch.id
    vendors = crud.get_vendors_by_branch(db, branch_id=active_branch_id, business_id=current_user.business_id)
    
    bills_for_vendor = []
    if vendor_id:
        bills_for_vendor = db.query(models.PurchaseBill).filter(
            models.PurchaseBill.vendor_id == vendor_id,
            models.PurchaseBill.branch_id == active_branch_id, # Filter by active branch
            models.PurchaseBill.status != 'Paid'
        ).all()

    selected_bill = None
    if bill_id:
        selected_bill = crud.get_purchase_bill(db, bill_id=bill_id, business_id=current_user.business_id)
        # Security check
        if selected_bill and selected_bill.branch_id != active_branch_id:
            raise HTTPException(status_code=403, detail="Bill does not belong to the active branch.")

    return templates.TemplateResponse("purchases/create_debit_note.html", {
        "request": request,
        "user": current_user,
        "user_perms": crud.get_user_permissions(current_user, db),
        "vendors": vendors,
        "selected_vendor_id": vendor_id,
        "bills_for_vendor": bills_for_vendor,
        "selected_bill": selected_bill,
        "title": "New Debit Note"
    })

@router.get("/debit-notes", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["purchases:view"]))])
async def get_debit_notes_history_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):

    debit_notes_objects = crud.get_debit_notes_by_business(db, business_id=current_user.business_id)
    
    debit_notes_data = jsonable_encoder(debit_notes_objects)
    
    user_perms = crud.get_user_permissions(current_user, db)

    return templates.TemplateResponse("purchases/debit_notes_history.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "debit_notes_data": debit_notes_data,
        "title": "Debit Note History"
    })


@router.get("/history", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["purchases:view"]))])
async def get_purchase_history_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    # For admins, show all bills. For others, it's implicitly filtered by their branch access.
    # We can add a filter dropdown on the frontend later if needed.
    active_branch = current_user.selected_branch
    bills_objects = crud.get_purchase_bills_by_business(db, business_id=current_user.business_id, branch_id=active_branch.id)
    
    bills_json = jsonable_encoder(bills_objects)
    
    user_perms = crud.get_user_permissions(current_user, db)
    
    return templates.TemplateResponse("purchases/purchase_history.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "bills_data": bills_json,
        "title": "Purchase History"
    })




@router.get("/debit-note/{debit_note_id}", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["purchases:view"]))])
async def get_debit_note_detail_page(
    debit_note_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):

    debit_note = db.query(models.DebitNote)\
        .options(
            joinedload(models.DebitNote.items).joinedload(models.DebitNoteItem.product),
            joinedload(models.DebitNote.vendor)
        )\
        .filter(
            models.DebitNote.id == debit_note_id,
            models.DebitNote.business_id == current_user.business_id
        )\
        .first()

    if not debit_note:
        raise HTTPException(status_code=404, detail="Debit Note not found or not accessible.")

    user_perms = crud.get_user_permissions(current_user, db)

    return templates.TemplateResponse("purchases/debit_note_detail.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "debit_note": debit_note,
        "title": f"Debit Note: {debit_note.debit_note_number}"
    })



@router.post("/preview-bill", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["purchases:create"]))])
async def handle_preview_purchase_bill(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    vendor_id: int = Form(...),
    bill_date: date = Form(...),
    due_date: date = Form(...),
    items_json: str = Form(...)
):
    vendor = crud.get_vendor(db, vendor_id=vendor_id, business_id=current_user.business_id)
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found.")

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

    next_bill_number = crud.get_next_purchase_bill_number(db, business_id=current_user.business_id)
    user_perms = crud.get_user_permissions(current_user, db)

    return templates.TemplateResponse("purchases/preview_purchase_bill.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "title": "Preview Purchase Bill",
        
        "vendor_id": vendor.id,
        "vendor_name": vendor.name,
        "bill_number": next_bill_number,
        "bill_date": bill_date,
        "due_date": due_date,
        "items_for_preview": enriched_items, 
        "total_amount": total_amount,

        "items_json_for_save": items_json
    })




@router.post("/new-bill", response_class=RedirectResponse, dependencies=[Depends(security.PermissionChecker(["purchases:create"]))])
async def handle_create_purchase_bill(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    vendor_id: int = Form(...),
    bill_date: date = Form(...),
    due_date: date = Form(...),
    items_json: str = Form(...)
):
    try:
        items_list = json.loads(items_json)
        if not items_list:
            raise HTTPException(status_code=400, detail="Cannot create an empty bill.")
        
        # Create Pydantic models for the items
        item_schemas = [schemas.PurchaseBillItemCreate(**item) for item in items_list]
        

        bill_schema = schemas.PurchaseBillCreate(
            vendor_id=vendor_id,
            bill_date=bill_date,
            due_date=due_date,
            items=item_schemas
        )
        
        # Now, pass the complete and validated schema to the CRUD function.
        crud.create_purchase_bill(
            db=db, 
            bill_data=bill_schema, 
            business_id=current_user.business_id, 
            branch_id=current_user.selected_branch.id
        )
        db.commit()
    except ValueError as e:
        db.rollback()
        # This will now catch specific errors from the CRUD function, like "Vendor not found."
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        # This will catch any other unexpected errors, like JSON decoding issues.
        print(f"Unexpected error in handle_create_purchase_bill: {e}") # Log for debugging
        raise HTTPException(status_code=500, detail="An unexpected error occurred while creating the purchase bill.")

    return RedirectResponse(url="/purchases/history", status_code=HTTP_303_SEE_OTHER)




@router.post("/record-payment", response_class=RedirectResponse, dependencies=[Depends(security.PermissionChecker(["purchases:edit"]))])
async def handle_record_payment(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    bill_id: int = Form(...),
    payment_date: date = Form(...),
    amount_paid: float = Form(...),
    payment_account_id: int = Form(...)
):
    bill = crud.get_purchase_bill(db, bill_id=bill_id, business_id=current_user.business_id)
    if not bill:
        raise HTTPException(status_code=404, detail="Purchase bill not found.")
    
    if bill.branch_id != current_user.selected_branch.id:
        raise HTTPException(status_code=403, detail="You can only record payments for bills in your active branch.")

    try:
        crud.record_payment_for_bill(
            db=db,
            bill=bill,
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
        raise HTTPException(status_code=500, detail="An unexpected error occurred while recording the payment.")

    return RedirectResponse(url=f"/crm/vendors/{bill.vendor_id}/view?tab=bills", status_code=HTTP_303_SEE_OTHER)



@router.post("/new-debit-note", response_class=RedirectResponse, dependencies=[Depends(security.PermissionChecker(["purchases:create_debit_note"]))])
async def handle_create_debit_note(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    original_bill_id: int = Form(...),
    debit_note_date: date = Form(...),
    product_id: list[int] = Form(...),
    price: list[float] = Form(...),
    return_quantity: list[float] = Form(...)
):
    original_bill = crud.get_purchase_bill(db, bill_id=original_bill_id, business_id=current_user.business_id)
    if not original_bill:
        raise HTTPException(status_code=404, detail="Original purchase bill not found.")

    if original_bill.branch_id != current_user.selected_branch.id:
        raise HTTPException(status_code=403, detail="You can only create debit notes for bills in your active branch.")

    items_to_return = []
    for i in range(len(product_id)):
        if float(return_quantity[i]) > 0:
            original_item = next((item for item in original_bill.items if item.product_id == int(product_id[i])), None)
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

        crud.create_debit_note_for_bill(
            db=db,
            original_bill=original_bill,
            debit_note_date=debit_note_date,
            items_to_return=items_to_return
        )
        db.commit()
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"A server error occurred: {str(e)}")

    return RedirectResponse(url=f"/crm/vendors/{original_bill.vendor_id}/view?tab=bills", status_code=HTTP_303_SEE_OTHER)



@router.get("/{bill_id}", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["purchases:view"]))])
async def get_purchase_bill_detail_page(
    request: Request,
    bill_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):

    bill = crud.get_purchase_bill(db, bill_id=bill_id, business_id=current_user.business_id)
    
    if not bill:
        raise HTTPException(status_code=404, detail="Purchase bill not found or not accessible.")
        
    user_perms = crud.get_user_permissions(current_user, db)
    
    return templates.TemplateResponse("purchases/purchase_bill_detail.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "bill": bill,
        "title": f"Purchase Bill {bill.bill_number}"
    })

