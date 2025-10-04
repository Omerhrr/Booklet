# In: app/routers/banking.py

from fastapi import APIRouter, Depends, Request, Form, HTTPException, Query, Response
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from sqlalchemy.orm import Session
from .. import crud, models, schemas, security
from ..database import get_db
from ..templating import templates
from datetime import date
from starlette.status import HTTP_303_SEE_OTHER
import json
from fastapi.encoders import jsonable_encoder
from typing import Optional

router = APIRouter(
    prefix="/banking",
    tags=["Banking"],
    dependencies=[Depends(security.get_current_active_user)]
)

@router.get("/accounts", response_class=HTMLResponse)
async def get_bank_accounts_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    """Renders the page for managing bank accounts for the selected branch."""
    bank_accounts = crud.banking.get_bank_accounts_by_branch(db, branch_id=current_user.selected_branch.id)
    user_perms = crud.get_user_permissions(current_user, db)
    
    return templates.TemplateResponse("banking/accounts.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "bank_accounts": bank_accounts,
        "title": "Bank Accounts"
    })

@router.post("/accounts", response_class=HTMLResponse)
async def handle_create_bank_account(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    account_name: str = Form(...),
    bank_name: str = Form(None),
    account_number: str = Form(None)
):
    """Handles the form submission for creating a new bank account."""
    account_schema = schemas.BankAccountCreate(
        account_name=account_name,
        bank_name=bank_name,
        account_number=account_number
    )
    try:
        new_account = crud.banking.create_bank_account(
            db, 
            account_data=account_schema, 
            business_id=current_user.business_id, 
            branch_id=current_user.selected_branch.id
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not create bank account. Error: {e}")

    return templates.TemplateResponse("banking/partials/account_row.html", {
        "request": request,
        "account": new_account
    })

@router.get("/transfers", response_class=HTMLResponse)
async def get_transfers_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    """Renders the page to manage and create fund transfers."""
    transfer_accounts = crud.banking.get_payment_accounts(db, business_id=current_user.business_id, branch_id=current_user.selected_branch.id)
    transfers = crud.banking.get_fund_transfers_by_branch(
        db, 
        business_id=current_user.business_id, 
        branch_id=current_user.selected_branch.id
    )
    user_perms = crud.get_user_permissions(current_user, db)

    return templates.TemplateResponse("banking/transfers.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "transfer_accounts": transfer_accounts,
        "transfers": transfers,
        "title": "Banking & Fund Transfers"
    })

@router.post("/transfers", response_class=RedirectResponse)
async def handle_create_transfer(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    transfer_date: date = Form(...),
    amount: float = Form(...),
    from_account_id: int = Form(...),
    to_account_id: int = Form(...),
    description: str = Form(...)
):
    """Handles the form submission for a new fund transfer."""
    transfer_data = {
        "transfer_date": transfer_date,
        "amount": amount,
        "from_account_id": from_account_id,
        "to_account_id": to_account_id,
        "description": description
    }
    
    try:
        crud.banking.create_fund_transfer(
            db, 
            transfer_data=transfer_data, 
            business_id=current_user.business_id, 
            branch_id=current_user.selected_branch.id
        )
        db.commit()
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to record fund transfer.")

    return RedirectResponse(url="/banking/transfers", status_code=HTTP_303_SEE_OTHER)

@router.get("/reconciliation", response_class=HTMLResponse)
async def get_reconciliation_landing_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    """Renders the new reconciliation landing page, showing a list of accounts."""
    bank_accounts = crud.banking.get_bank_accounts_by_branch(db, branch_id=current_user.selected_branch.id)
    user_perms = crud.get_user_permissions(current_user, db)
    return templates.TemplateResponse("banking/reconciliation_landing.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "bank_accounts": bank_accounts,
        "title": "Bank Reconciliation"
    })

@router.get("/reconciliation/{account_id}", response_class=HTMLResponse)
async def get_reconciliation_workspace_page(
    account_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    """Renders the new, dedicated reconciliation workspace for a specific account."""
    account = crud.account.get_account_by_id(db, account_id=account_id, business_id=current_user.business_id)
    if not account or account.bank_account_details is None:
        raise HTTPException(status_code=404, detail="Bank account not found.")

    transactions = crud.banking.get_unreconciled_transactions(db, account_id=account_id, branch_id=current_user.selected_branch.id)
    opening_balance = crud.banking.get_opening_balance_for_reconciliation(db, account_id=account_id)
    user_perms = crud.get_user_permissions(current_user, db)
    return templates.TemplateResponse("banking/reconciliation_workspace.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "account": account,
        "transactions_json": jsonable_encoder(transactions),
        "opening_balance": opening_balance,
        "title": f"Reconcile: {account.name}"
    })

@router.post("/reconciliation/{account_id}", response_class=RedirectResponse)
async def handle_process_reconciliation(
    account_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    statement_date: date = Form(...),
    statement_balance: float = Form(...),
    cleared_ids_json: str = Form(...)
):
    """Handles the submission of a completed reconciliation."""
    try:
        cleared_ids = json.loads(cleared_ids_json) if cleared_ids_json.strip() else []
        if not isinstance(cleared_ids, list):
            raise ValueError("Invalid data format.")
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid format for cleared transaction IDs.")

    try:
        reconciliation = crud.banking.process_reconciliation(
            db=db,
            business_id=current_user.business_id,
            branch_id=current_user.selected_branch.id,
            account_id=account_id,
            statement_date=statement_date,
            statement_balance=statement_balance,
            cleared_transaction_ids=cleared_ids
        )
        db.commit()
        # Redirect to the new report page
        return RedirectResponse(url=f"/banking/reconciliation/{reconciliation.id}/report", status_code=HTTP_303_SEE_OTHER)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to process reconciliation: {e}")

@router.get("/reconciliation/{account_id}", response_class=HTMLResponse)
async def get_reconciliation_workspace_page(
    account_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    """Renders the new, dedicated reconciliation workspace for a specific account."""
    account = crud.account.get_account_by_id(db, account_id=account_id, business_id=current_user.business_id)
    if not account or account.bank_account_details is None:
        raise HTTPException(status_code=404, detail="Bank account not found.")

    transactions = crud.banking.get_unreconciled_transactions(db, account_id=account_id, branch_id=current_user.selected_branch.id)
    opening_balance = crud.banking.get_opening_balance_for_reconciliation(db, account_id=account_id)
    
    # THE FIX: Ensure user_perms is always passed so the layout doesn't break.
    user_perms = crud.get_user_permissions(current_user, db)

    return templates.TemplateResponse("banking/reconciliation_workspace.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms, # <-- THIS IS CRITICAL FOR THE SIDEBAR
        "account": account,
        "transactions_json": jsonable_encoder(transactions),
        "opening_balance": opening_balance,
        "title": f"Reconcile: {account.name}"
    })

@router.get("/reconciliation/{reconciliation_id}/report", response_class=HTMLResponse)
async def get_reconciliation_report_page(
    reconciliation_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    """Displays a summary report of a completed reconciliation."""
    report_data = crud.banking.get_reconciliation_report_data(db, reconciliation_id, current_user.business_id)
    if not report_data:
        raise HTTPException(status_code=404, detail="Reconciliation report not found.")
        
    user_perms = crud.get_user_permissions(current_user, db)

    return templates.TemplateResponse("banking/reconciliation_report.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "report_data": report_data,
        "title": f"Reconciliation Report for {report_data['account'].name}"
    })

@router.get("/accounts/{account_id}", response_class=HTMLResponse)
async def get_bank_account_detail_page(
    account_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None)
):
    account = crud.account.get_account_by_id(db, account_id=account_id, business_id=current_user.business_id)
    if not account or account.bank_account_details is None:
        raise HTTPException(status_code=404, detail="Bank account not found.")

    ledger, opening_balance, closing_balance = crud.ledger.get_account_ledger(
        db, 
        account_id=account_id, 
        branch_id=current_user.selected_branch.id,
        start_date=start_date,
        end_date=end_date
    )
    user_perms = crud.get_user_permissions(current_user, db)

    return templates.TemplateResponse("banking/account_detail.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "account": account,
        "ledger": ledger,
        "opening_balance": opening_balance,
        "closing_balance": closing_balance,
        "filters": {"start_date": start_date, "end_date": end_date},
        "title": f"Ledger for {account.name}"
    })

# NEW ENDPOINT: For exporting the ledger to Excel
@router.get("/accounts/{account_id}/export/excel")
async def export_bank_ledger_excel(
    account_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None)
):
    if start_date is None and end_date is None:
        # We can't easily show a toast here, so returning an error response is appropriate.
        return Response(content="Error: Please select a start date or an end date.", status_code=400)
    account = crud.get_account_by_id(db, account_id=account_id, business_id=current_user.business_id)
    if not account: raise HTTPException(404)

    ledger, _, _ = crud.get_account_ledger(db, account_id, current_user.selected_branch.id, start_date, end_date)

    headers = ["Date", "Description", "Debit", "Credit", "Balance"]
    data_to_export = [
        [
            item["entry"].transaction_date.strftime('%Y-%m-%d'),
            item["entry"].description,
            item["entry"].debit,
            item["entry"].credit,
            item["balance"]
        ] for item in ledger
    ]
    
    excel_buffer = crud.export_to_excel(headers, data_to_export, f"Statement for {account.name}")
    
    return StreamingResponse(
        excel_buffer,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f'attachment; filename="statement_{account.name}_{date.today()}.xlsx"'}
    )

# NEW ENDPOINT: For exporting the ledger to PDF
@router.get("/accounts/{account_id}/export/pdf", response_class=Response) # Use Response for PDF
async def export_bank_ledger_pdf(
    account_id: int,
    request: Request, # Request is needed for templates
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None)
):
    if start_date is None and end_date is None:
        raise HTTPException(status_code=400, detail="Please select a start date or an end date to generate a statement.")
    account = crud.account.get_account_by_id(db, account_id=account_id, business_id=current_user.business_id)
    if not account: raise HTTPException(404)

    # We will handle the date validation in Part 2
    
    ledger, opening_balance, closing_balance = crud.ledger.get_account_ledger(db, account_id, current_user.selected_branch.id, start_date, end_date)

    # THE FIX: The generic template expects 'target'. We also need to adapt the account object
    # to have a 'name' attribute for the template to use.
    class ReportTarget:
        def __init__(self, name, address=None):
            self.name = name
            self.address = address

    report_target = ReportTarget(name=account.name, address=current_user.business.name)


    context = {
        "request": request,
        "business": current_user.business,
        "target": report_target, # <-- Pass the adapted object as 'target'
        "lines": ledger,
        "opening_balance": opening_balance,
        "closing_balance": closing_balance,
        "start_date": start_date,
        "end_date": end_date,
        "statement_type": "Bank Account"
    }

    pdf_buffer = crud.reports.render_html_to_pdf("reports/pdf/statement_template.html", context, templates)

    return Response(
        pdf_buffer.read(),
        media_type='application/pdf',
        headers={'Content-Disposition': f'inline; filename="statement_{account.name}_{date.today()}.pdf"'}
    )

