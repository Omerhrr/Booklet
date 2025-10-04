from fastapi import APIRouter, Depends, Request, Form, HTTPException
from starlette.responses import RedirectResponse
from starlette.status import HTTP_303_SEE_OTHER
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, Response
from .. import crud, models, security
from ..database import get_db
from ..templating import templates

router = APIRouter(
    prefix="/expenses",
    tags=["Expenses"],
    dependencies=[Depends(security.get_current_active_user)]
)


@router.get("/new", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["expenses:create"]))])
async def get_new_expense_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    """Renders the page with the form to create a new expense."""
    if current_user.is_superuser:
        branches_for_user = crud.get_branches_by_business(db, business_id=current_user.business_id)
    else:
        branches_for_user = [assignment.branch for assignment in current_user.roles]

    expense_accounts = crud.get_expense_accounts(db, business_id=current_user.business_id)
    payment_accounts = crud.get_payment_accounts(
        db, 
        business_id=current_user.business_id, 
        branch_id=current_user.selected_branch.id
    )
    # payment_accounts = crud.get_payment_accounts(db, business_id=current_user.business_id)
    vendors = crud.get_vendors_by_business(db, business_id=current_user.business_id)

    return templates.TemplateResponse("expenses/new_expense.html", {
        "request": request,
        "user": current_user,
        "user_perms": crud.get_user_permissions(current_user, db),
        "expense_accounts": expense_accounts,
        "payment_accounts": payment_accounts,
        "vendors": vendors,
        "branches": branches_for_user,
        "title": "Record New Expense"
    })

@router.get("/history", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["expenses:view"]))])
async def get_expense_history_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    """Renders the searchable history of all expenses for the selected branch."""
    
    # THE FIX: Call the new branch-specific function
    expenses_objects = crud.get_expenses_by_branch(
        db, 
        business_id=current_user.business_id,
        branch_id=current_user.selected_branch.id 
    )
    expenses_data_json = jsonable_encoder(expenses_objects)

    return templates.TemplateResponse("expenses/expense_history.html", {
        "request": request,
        "user": current_user,
        "user_perms": crud.get_user_permissions(current_user, db),
        "expenses_data": expenses_data_json,
        "title": "Expense History"
    })


@router.post("/new", response_class=RedirectResponse, dependencies=[Depends(security.PermissionChecker(["expenses:create"]))])
async def handle_create_expense(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    expense_date: date = Form(...),
    sub_total: float = Form(...), # Changed from 'amount'
    vat_amount: float = Form(0.0),
    expense_account_id: int = Form(...),
    paid_from_account_id: int = Form(...),
    branch_id: int = Form(...),
    description: str = Form(...),
    vendor_id_str: Optional[str] = Form(None)
):
    """Handles the form submission and redirects to the history page."""
    vendor_id = int(vendor_id_str) if vendor_id_str else None
    
    user_branch_ids = {b.id for b in current_user.business.branches}
    if branch_id not in user_branch_ids:
        raise HTTPException(status_code=403, detail="Branch not accessible.")

    expense_account = db.query(models.Account).filter_by(id=expense_account_id, business_id=current_user.business_id).first()
    if not expense_account or expense_account.type != models.AccountType.EXPENSE:
        raise HTTPException(status_code=400, detail="Invalid expense category selected.")

    expense_data = {
        "expense_date": expense_date, 
        "sub_total": sub_total,
        "vat_amount": vat_amount,
        "description": description, 
        "paid_from_account_id": paid_from_account_id,
        "expense_account_id": expense_account_id, 
        "vendor_id": int(vendor_id_str) if vendor_id_str else None,
        "branch_id": branch_id, 
        "business_id": current_user.business_id
    }
    
    try:
        crud.create_expense(db, expense_data=expense_data)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to record expense: {e}")

    return RedirectResponse(url="/expenses/history", status_code=HTTP_303_SEE_OTHER)

@router.delete("/history/{expense_id}", status_code=200, dependencies=[Depends(security.PermissionChecker(["expenses:delete"]))])
async def handle_delete_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    """Handles the deletion of an expense and the reversal of its ledger entries."""
    # 1. Find the expense and verify ownership
    expense_to_delete = crud.get_expense_by_id(db, expense_id=expense_id, business_id=current_user.business_id)
    
    if not expense_to_delete:
        raise HTTPException(status_code=404, detail="Expense not found or not accessible.")
        
    try:

        crud.delete_expense_and_reverse_ledger(db, expense=expense_to_delete)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete expense: {e}")
    return Response(status_code=200)