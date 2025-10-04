
from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from .. import crud, models, security
from ..database import get_db
from ..templating import templates
from datetime import date
from starlette.status import HTTP_303_SEE_OTHER

router = APIRouter(
    prefix="/other-income",
    tags=["Accounting"],
    dependencies=[Depends(security.get_current_active_user), Depends(security.PermissionChecker(["accounting:create"]))]
)

@router.get("/history", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["accounting:view"]))])
async def get_other_income_history_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    """Renders the history of all 'Other Income' transactions for the selected branch."""
    incomes = crud.get_other_incomes_by_branch(
        db, 
        business_id=current_user.business_id, 
        branch_id=current_user.selected_branch.id
    )
    user_perms = crud.get_user_permissions(current_user, db)

    return templates.TemplateResponse("other_income/history.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "incomes": incomes,
        "title": "Other Income History"
    })

@router.get("/new", response_class=HTMLResponse)
async def get_new_other_income_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    """Renders the form to create a new 'Other Income' record."""
    income_accounts = crud.get_other_income_accounts(db, business_id=current_user.business_id)
    # payment_accounts = crud.get_payment_accounts(db, business_id=current_user.business_id)
    payment_accounts = crud.banking.get_payment_accounts(
        db, 
        business_id=current_user.business_id, 
        branch_id=current_user.selected_branch.id
    )
    user_perms = crud.get_user_permissions(current_user, db)

    return templates.TemplateResponse("other_income/new.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "income_accounts": income_accounts,
        "payment_accounts": payment_accounts,
        "title": "Record Other Income"
    })

@router.post("/new", response_class=RedirectResponse)
async def handle_create_other_income(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    income_date: date = Form(...),
    amount: float = Form(...),
    income_account_id: int = Form(...),
    deposited_to_account_id: int = Form(...),
    description: str = Form(...)
):
    """Handles the form submission for a new 'Other Income' record."""
    income_data = {
        "income_date": income_date,
        "amount": amount,
        "income_account_id": income_account_id,
        "deposited_to_account_id": deposited_to_account_id,
        "description": description
    }
    
    try:
        crud.create_other_income(
            db, 
            income_data=income_data, 
            business_id=current_user.business_id, 
            branch_id=current_user.selected_branch.id
        )
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error creating other income: {e}")
        raise HTTPException(status_code=500, detail="Failed to record income.")

    return RedirectResponse(url="/other-income/history", status_code=HTTP_303_SEE_OTHER)
