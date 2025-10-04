
from fastapi import APIRouter, Depends, Request, Response, Form, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from .. import crud, models, schemas, security
from ..database import get_db
from ..templating import templates
from fastapi.encoders import jsonable_encoder 
router = APIRouter(
    prefix="/crm/vendors",
    tags=["Vendors"],
    dependencies=[Depends(security.get_current_active_user), Depends(security.PermissionChecker(["vendors:view"]))] 
)

@router.get("/", response_class=HTMLResponse)
async def get_vendors_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    # Logic is now simplified, using the globally selected branch
    selected_branch = current_user.selected_branch
    
    vendors = crud.get_vendors_by_branch(
        db, 
        branch_id=selected_branch.id, 
        business_id=current_user.business_id
    )
    
    user_perms = crud.get_user_permissions(current_user, db)

    return templates.TemplateResponse(
        "crm/vendors.html",
        {
            "request": request,
            "user": current_user,
            "vendors": vendors,
            "user_perms": user_perms,
            "selected_branch": selected_branch, 
            "title": "Vendors"
        }
    )


@router.post("/", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["vendors:create"]))])
async def handle_create_vendor(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    name: str = Form(...),
    email: str = Form(None),
    phone: str = Form(None),
    address: str = Form(None)
):
    # The branch_id is now taken from the user's active context
    branch_id = current_user.selected_branch.id

    vendor_schema = schemas.VendorCreate(
        name=name, 
        email=email, 
        phone=phone, 
        address=address, 
        branch_id=branch_id, 
        business_id=current_user.business_id
    )
    new_vendor = crud.create_vendor(db, vendor=vendor_schema)

    user_perms = crud.get_user_permissions(current_user, db)
    return templates.TemplateResponse("crm/partials/vendor_row.html", {
        "request": request, 
        "vendor": new_vendor,
        "user_perms": user_perms
    })



@router.get("/{vendor_id}/edit", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["vendors:edit"]))]) 
async def get_edit_vendor_form(
    vendor_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    vendor = crud.get_vendor(db, vendor_id=vendor_id, business_id=current_user.business_id)
    if not vendor or vendor.branch.business_id != current_user.business_id:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return templates.TemplateResponse("crm/partials/vendor_row_edit.html", {"request": request, "vendor": vendor})

@router.get("/{vendor_id}", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["vendors:view"]))]) 
async def get_vendor_row(
    vendor_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    
    vendor = crud.get_vendor(db, vendor_id=vendor_id, business_id=current_user.business_id)
    if not vendor or vendor.branch.business_id != current_user.business_id:
        raise HTTPException(status_code=404, detail="Vendor not found")
    
    user_perms = crud.get_user_permissions(current_user, db)
    return templates.TemplateResponse("crm/partials/vendor_row.html", {
        "request": request, 
        "vendor": vendor,
        "user_perms": user_perms
    })

@router.put("/{vendor_id}", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["vendors:edit"]))]) 
async def handle_update_vendor(
    vendor_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    name: str = Form(...),
    email: str = Form(None),
    phone: str = Form(None),
    address: str = Form(None)
):
    vendor_update = schemas.VendorUpdate(name=name, email=email, phone=phone, address=address)
    updated_vendor = crud.update_vendor(db, vendor_id=vendor_id, business_id=current_user.business_id, vendor_update=vendor_update)
    
    if not updated_vendor:
        raise HTTPException(status_code=404, detail="Vendor not found or not accessible.")

    user_perms = crud.get_user_permissions(current_user, db)
    return templates.TemplateResponse("crm/partials/vendor_row.html", {
        "request": request, 
        "vendor": updated_vendor,
        "user_perms": user_perms
    })

@router.delete("/{vendor_id}", response_class=Response, dependencies=[Depends(security.PermissionChecker(["vendors:delete"]))]) 
async def handle_delete_vendor(
    vendor_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    success = crud.delete_vendor(db, vendor_id=vendor_id, business_id=current_user.business_id)

    if not success:
        raise HTTPException(status_code=404, detail="Vendor not found or not accessible.")
    return Response(status_code=200)



@router.get("/{vendor_id}/view", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["vendors:view"]))])
async def get_vendor_detail_page(
    vendor_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    vendor = crud.get_vendor(db, vendor_id=vendor_id, business_id=current_user.business_id)
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")


    all_bills_objects = crud.get_purchase_bills_by_vendor(db, vendor_id=vendor.id, business_id=current_user.business_id)
    ledger_entries_objects, final_balance = crud.get_vendor_ledger(db, vendor_id=vendor.id, business_id=current_user.business_id)
    # payment_accounts = crud.get_payment_accounts(db, business_id=current_user.business_id)
    payment_accounts = crud.banking.get_payment_accounts(
        db, 
        business_id=current_user.business_id, 
        branch_id=vendor.branch_id
    )
  
    bills_data_json = jsonable_encoder(all_bills_objects)
    ledger_data_json = jsonable_encoder(ledger_entries_objects)

    unpaid_bills_objects = [bill for bill in all_bills_objects if bill.status != 'Paid']
    payable_bills_data_json = jsonable_encoder(unpaid_bills_objects)

    user_perms = crud.get_user_permissions(current_user, db)

    return templates.TemplateResponse("crm/vendor_detail.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "vendor": vendor,

        "bills_data": bills_data_json,
        "ledger_data": ledger_data_json,
 
        "payable_bills_data": payable_bills_data_json,
        "payment_accounts": payment_accounts,
        
        "final_balance": final_balance,
        "title": f"Vendor: {vendor.name}"
    })
