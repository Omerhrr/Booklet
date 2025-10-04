
from fastapi import APIRouter, Depends, Request, Form, HTTPException, Response 
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from .. import crud, models, schemas, security
from ..database import get_db
from ..templating import templates 
from fastapi.encoders import jsonable_encoder
router = APIRouter(
    prefix="/crm/customers",
    tags=["CRM"],
    dependencies=[Depends(security.get_current_active_user), Depends(security.PermissionChecker(["customers:view"]))]
)
@router.get("/", response_class=HTMLResponse)
async def get_customers_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    # The logic is now much simpler. The selected branch is already on the user object.
    selected_branch = current_user.selected_branch
    
    customers = crud.get_customers_by_branch(
        db, 
        branch_id=selected_branch.id, 
        business_id=current_user.business_id
    )
    
    user_perms = crud.get_user_permissions(current_user, db)

    return templates.TemplateResponse(
        "crm/customers.html",
        {
            "request": request,
            "user": current_user,
            "customers": customers,
            "user_perms": user_perms,
            # Pass the selected branch to the template for display
            "selected_branch": selected_branch, 
            "title": "Customers"
        }
    )

@router.post("/", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["customers:create"]))])
async def handle_create_customer(
    request: Request, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(security.get_current_active_user), 
    name: str = Form(...), 
    email: str = Form(...), 
    phone: str = Form(...), 
    address: str = Form(None),
):
    # Create the customer in the currently selected branch
    branch_id = current_user.selected_branch.id

    customer_schema = schemas.CustomerCreate(
        name=name, 
        email=email, 
        phone=phone,
        branch_id=branch_id,
        address=address,
        business_id=current_user.business_id
    )
    new_customer = crud.create_customer(db, customer=customer_schema)
    
    # Pass necessary context to the partial
    user_perms = crud.get_user_permissions(current_user, db)
    return templates.TemplateResponse("crm/partials/customer_row.html", {
        "request": request, 
        "customer": new_customer,
        "user_perms": user_perms
    })


@router.get("/{customer_id}/edit", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["customers:edit"]))])
async def get_edit_customer_form(
    customer_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    """
    Returns an HTML partial with input fields to edit a customer's details.
    """
    customer = crud.get_customer(db, customer_id=customer_id, business_id=current_user.business_id) 
    if not customer or customer.branch.business_id != current_user.business_id:
        raise HTTPException(status_code=404, detail="Customer not found")

    return templates.TemplateResponse(
        "crm/partials/customer_row_edit.html",
        {"request": request, "customer": customer}
    )

@router.put("/{customer_id}", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["customers:edit"]))])
async def handle_update_customer(
    customer_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    address: str = Form(None)
):
    """
    Handles the submission of the edit form, updating the customer in the DB.
    """
    customer_update = schemas.CustomerUpdate(name=name, email=email, phone=phone, address=address) # Requires new schema

    updated_customer = crud.update_customer(db, customer_id=customer_id, customer_update=customer_update, business_id=current_user.business_id)
    if not updated_customer:
        raise HTTPException(status_code=404, detail="Customer not found or not accessible.")

    user_perms = crud.get_user_permissions(current_user, db)
    return templates.TemplateResponse("crm/partials/customer_row.html", {
        "request": request, 
        "customer": updated_customer,
        "user_perms": user_perms
    })


@router.get("/{customer_id}", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["customers:view"]))])
async def get_customer_row(
    customer_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    """
    Returns a single, non-editable customer row. Used for cancelling an edit.
    """
    customer = crud.get_customer(db, customer_id=customer_id, business_id=current_user.business_id)
    if not customer or customer.branch.business_id != current_user.business_id:
        raise HTTPException(status_code=404, detail="Customer not found")

    user_perms = crud.get_user_permissions(current_user, db)
    return templates.TemplateResponse("crm/partials/customer_row.html", {
        "request": request, 
        "customer": customer,
        "user_perms": user_perms
    })


@router.delete("/{customer_id}", response_class=Response, dependencies=[Depends(security.PermissionChecker(["customers:delete"]))])
async def handle_delete_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    """
    Deletes a customer from the database.
    """
    success = crud.delete_customer(db, customer_id=customer_id, business_id=current_user.business_id)
    if not success:
        raise HTTPException(status_code=404, detail="Customer not found or not accessible.")

    return Response(status_code=200)




@router.get("/{customer_id}/view", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["customers:view"]))])
async def get_customer_detail_page(
    request: Request,
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    customer = crud.get_customer(db, customer_id=customer_id, business_id=current_user.business_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")


    all_invoices_objects = crud.get_sales_invoices_by_customer(db, customer_id=customer.id, business_id=current_user.business_id)
    ledger_entries_objects, final_balance = crud.get_customer_ledger(db, customer_id=customer.id, business_id=current_user.business_id)
    # payment_accounts = crud.get_payment_accounts(db, business_id=current_user.business_id)
    payment_accounts = crud.banking.get_payment_accounts(
        db, 
        business_id=current_user.business_id, 
        branch_id=customer.branch_id
    )
 
    invoices_data_json = jsonable_encoder(all_invoices_objects)
    ledger_data_json = jsonable_encoder(ledger_entries_objects)

    unpaid_invoices_objects = [inv for inv in all_invoices_objects if inv.status != 'Paid']
    receivable_invoices_json = jsonable_encoder(unpaid_invoices_objects)

    user_perms = crud.get_user_permissions(current_user, db)

    return templates.TemplateResponse("crm/customer_detail.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "customer": customer,

        "invoices_data": invoices_data_json,
        "ledger_data": ledger_data_json,

        "receivable_invoices_data": receivable_invoices_json,
        "payment_accounts": payment_accounts,
        
        "final_balance": final_balance,
        "title": f"Customer: {customer.name}"
    })
