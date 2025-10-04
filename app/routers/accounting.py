# app/routers/accounting.py
from starlette.responses import RedirectResponse
from fastapi import APIRouter, Depends, Request, HTTPException, Form, Query
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session
from .. import crud, models, schemas, security
from ..database import get_db
from ..templating import templates
from itertools import groupby
from datetime import date
from starlette.status import HTTP_303_SEE_OTHER
from typing import Optional
router = APIRouter(
    prefix="/accounting",
    tags=["Accounting"],
    dependencies=[Depends(security.get_current_active_user), Depends(security.PermissionChecker(["accounting:view"]))]
)

@router.get("/chart-of-accounts", response_class=HTMLResponse)
async def get_chart_of_accounts_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    accounts = crud.get_chart_of_accounts(db, business_id=current_user.business_id)
    user_perms = crud.get_user_permissions(current_user, db)
    accounts_by_type = {k.value: list(v) for k, v in groupby(accounts, key=lambda acc: acc.type)}

    return templates.TemplateResponse("accounting/chart_of_accounts.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "accounts_by_type": accounts_by_type,
        "account_types": [e.value for e in models.AccountType], 
        "title": "Chart of Accounts"
    })

@router.get("/chart-of-accounts/new-form", response_class=HTMLResponse)
async def get_new_account_form(request: Request):
    """Returns a fresh form partial for the modal."""
    return templates.TemplateResponse("accounting/partials/add_account_form.html", {
        "request": request,
        "account_types": [e.value for e in models.AccountType]
    })


@router.post("/chart-of-accounts", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["accounting:create"]))])
async def handle_create_account(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    name: str = Form(...),
    type: models.AccountType = Form(...)
):
    account_schema = schemas.AccountCreate(name=name, type=type)
    new_account = crud.create_account(db, account=account_schema, business_id=current_user.business_id)
    
    user_perms = crud.get_user_permissions(current_user, db)
    new_row_html = templates.TemplateResponse("accounting/partials/account_row.html", {
        "request": request, 
        "account": new_account,
        "user_perms": user_perms
    }).body.decode("utf-8")

    fresh_form_html = templates.TemplateResponse("accounting/partials/add_account_form.html", {
        "request": request,
        "account_types": [e.value for e in models.AccountType]
    }).body.decode("utf-8")

    html_response = f"""
    <tr id="account-table-{new_account.type.value}" hx-swap-oob="beforeend">{new_row_html}</tr>
    <div id="add-account-form-container" hx-swap-oob="innerHTML">{fresh_form_html}</div>
    """
    
    return HTMLResponse(content=html_response)

@router.get("/general-ledger", response_class=HTMLResponse)
async def get_general_ledger_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    account_id: Optional[int] = Query(None)
):
    entries = crud.get_general_ledger(
        db, 
        business_id=current_user.business_id, 
        branch_id=current_user.selected_branch.id,
        start_date=start_date, 
        end_date=end_date, 
        account_id=account_id
    )
    accounts = crud.get_chart_of_accounts(db, business_id=current_user.business_id)
    user_perms = crud.get_user_permissions(current_user, db)
    return templates.TemplateResponse("accounting/general_ledger.html", {
        "request": request, "user": current_user, "user_perms": user_perms,
        "entries": entries, "accounts": accounts,
        "filters": { "start_date": start_date, "end_date": end_date, "account_id": account_id },
        "title": "General Ledger"
    })

@router.get("/cashbook", response_class=HTMLResponse)
async def get_cashbook_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    account_id: Optional[int] = Query(None) # This can now be a specific bank account ID
):
    branch_id = current_user.selected_branch.id
    
    entries_with_balance, final_balance = crud.get_cashbook(
        db,
        business_id=current_user.business_id,
        branch_id=branch_id,
        start_date=start_date,
        end_date=end_date,
        account_id=account_id
    )
    
    # THE FIX: Populate the filter dropdown with the correct, branch-specific accounts.
    payment_accounts = crud.banking.get_payment_accounts(
        db, 
        business_id=current_user.business_id, 
        branch_id=branch_id
    )
    
    user_perms = crud.get_user_permissions(current_user, db)
    
    return templates.TemplateResponse("accounting/cashbook.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "entries_with_balance": entries_with_balance,
        "final_balance": final_balance,
        "payment_accounts": payment_accounts, # Pass the correct list to the template
        "filters": { "start_date": start_date, "end_date": end_date, "account_id": account_id },
        "title": "Cashbook"
    })

@router.get("/profit-and-loss", response_class=HTMLResponse)
async def get_profit_and_loss_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    start_date: date = Query(date.today().replace(day=1)),
    end_date: date = Query(date.today())
):
    report_data = crud.get_profit_and_loss_data(
        db,
        business_id=current_user.business_id,
        branch_id=current_user.selected_branch.id, # Pass the selected branch
        start_date=start_date,
        end_date=end_date
    )
    
    user_perms = crud.get_user_permissions(current_user, db)
    
    return templates.TemplateResponse("accounting/profit_and_loss.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "report_data": report_data,
        "filters": { "start_date": start_date, "end_date": end_date },
        "title": "Profit & Loss Statement"
    })

@router.get("/chart-of-accounts/{account_id}/edit", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["accounting:edit"]))])
async def get_edit_account_form(account_id: int, request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(security.get_current_active_user)):
    account = crud.get_account_by_id(db, account_id=account_id, business_id=current_user.business_id)
    if not account or account.is_system_account:
        raise HTTPException(status_code=403, detail="This account cannot be edited.")
    return templates.TemplateResponse("accounting/partials/account_row_edit.html", {"request": request, "account": account})

@router.put("/chart-of-accounts/{account_id}", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["accounting:edit"]))])
async def handle_update_account(
    account_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    name: str = Form(...)
):
    account_update = schemas.AccountUpdate(name=name)
    updated_account = crud.update_account(db, account_id=account_id, account_update=account_update, business_id=current_user.business_id)
    if not updated_account:
        raise HTTPException(status_code=404, detail="Account not found or cannot be updated.")
    user_perms = crud.get_user_permissions(current_user, db)
    return templates.TemplateResponse("accounting/partials/account_row.html", {"request": request, "account": updated_account, "user_perms": user_perms})

@router.delete("/chart-of-accounts/{account_id}", status_code=200, dependencies=[Depends(security.PermissionChecker(["accounting:delete"]))])
async def handle_delete_account(account_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(security.get_current_active_user)):

    success = crud.delete_account(db, account_id=account_id, business_id=current_user.business_id)
    if not success:

        response = Response(status_code=400)
        toast_event = {
            "show-toast": {
                "message": "Cannot delete account. It may be a system account or have transactions.",
                "type": "error"
            }
        }
        response.headers["HX-Trigger"] = json.dumps(toast_event)
        return response
    return Response(status_code=200)

@router.get("/payroll-liabilities", response_class=HTMLResponse)
async def get_payroll_liabilities_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    branch_id = current_user.selected_branch.id
    business_id = current_user.business_id

    # Fetch data for all three liability accounts
    paye_entries, paye_balance = crud.get_statutory_liability_ledger(db, business_id, branch_id, "PAYE Payable")
    pension_entries, pension_balance = crud.get_statutory_liability_ledger(db, business_id, branch_id, "Pension Payable")
    
    # NEW: Fetch data for Net Pay liability
    net_pay_entries, net_pay_balance = crud.get_statutory_liability_ledger(db, business_id, branch_id, "Payroll Liabilities")

    payment_accounts = crud.banking.get_payment_accounts(db, business_id, branch_id)
    user_perms = crud.get_user_permissions(current_user, db)
    
    return templates.TemplateResponse("accounting/payroll_liabilities.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "paye_entries": paye_entries,
        "paye_balance": paye_balance,
        "pension_entries": pension_entries,
        "pension_balance": pension_balance,
        "net_pay_entries": net_pay_entries,
        "net_pay_balance": net_pay_balance,
        "payment_accounts": payment_accounts,
        "title": "Payroll Liabilities"
    })

@router.post("/payroll-liabilities/pay", response_class=RedirectResponse)
async def handle_pay_payroll_liability(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    payment_date: date = Form(...),
    amount: float = Form(...),
    paid_from_account_id: int = Form(...),
    description: str = Form(...),
    liability_account_name: str = Form(...)
):
    # THE FIX: Add "Payroll Liabilities" to the list of valid accounts
    if liability_account_name not in ["PAYE Payable", "Pension Payable", "Payroll Liabilities"]:
        raise HTTPException(status_code=400, detail="Invalid liability account specified.")

    liability_account = db.query(models.Account).filter(
        models.Account.business_id == current_user.business_id, 
        models.Account.name == liability_account_name
    ).first()
    
    if not liability_account:
        raise HTTPException(status_code=400, detail=f"{liability_account_name} account not found.")

    asset_account = crud.get_account_by_id(db, account_id=paid_from_account_id, business_id=current_user.business_id)
    if not asset_account:
        raise HTTPException(status_code=400, detail="Payment account not found.")

    branch_id = current_user.selected_branch.id

    try:
        # Debit the liability account to reduce what is owed
        db.add(models.LedgerEntry(
            transaction_date=payment_date, 
            description=description,
            debit=amount, 
            account_id=liability_account.id,
            branch_id=branch_id
        ))
        
        # Credit the asset account (Cash/Bank) from which the payment was made
        db.add(models.LedgerEntry(
            transaction_date=payment_date, 
            description=description,
            credit=amount, 
            account_id=asset_account.id,
            branch_id=branch_id
        ))
        
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to record payment: {e}")

    # Redirect back to the newly named page
    return RedirectResponse(url="/accounting/payroll-liabilities", status_code=HTTP_303_SEE_OTHER)

@router.get("/balance-sheet", response_class=HTMLResponse)
async def get_balance_sheet_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    as_of_date: date = Query(date.today())
):
    report_data = crud.get_balance_sheet_data(
        db,
        business_id=current_user.business_id,
        branch_id=current_user.selected_branch.id, # Pass the selected branch
        as_of_date=as_of_date
    )
    
    user_perms = crud.get_user_permissions(current_user, db)
    
    return templates.TemplateResponse("accounting/balance_sheet.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "report_data": report_data,
        "as_of_date": as_of_date,
        "title": "Balance Sheet"
    })
