# app/routers/journal.py

from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session, joinedload 
from .. import crud, models, security
from ..database import get_db
from ..templating import templates
from datetime import date
import json
from starlette.status import HTTP_303_SEE_OTHER

router = APIRouter(
    prefix="/accounting/journal",
    tags=["Accounting"],
    dependencies=[Depends(security.get_current_active_user), Depends(security.PermissionChecker(["accounting:create"]))]
)

@router.get("/history", response_class=HTMLResponse)
async def get_journal_history_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    """Renders the history of all manual journal entries for the selected branch."""
    vouchers = crud.journal.get_journal_vouchers_by_branch(
        db, 
        business_id=current_user.business_id, 
        branch_id=current_user.selected_branch.id
    )
    return templates.TemplateResponse("accounting/journal/history.html", {
        "request": request,
        "user": current_user,
        "user_perms": crud.get_user_permissions(current_user, db),
        "vouchers": vouchers,
        "title": "Journal Entry History"
    })

@router.get("/new", response_class=HTMLResponse)
async def get_new_journal_entry_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    """Renders the dynamic form for creating a new journal entry."""
    accounts = crud.get_chart_of_accounts(db, business_id=current_user.business_id)
    return templates.TemplateResponse("accounting/journal/create.html", {
        "request": request,
        "user": current_user,
        "user_perms": crud.get_user_permissions(current_user, db),
        "accounts": accounts,
        "title": "New Journal Entry"
    })


@router.post("/preview", response_class=HTMLResponse)
async def handle_preview_journal_entry(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    transaction_date: date = Form(...),
    description: str = Form(...),
    entries_json: str = Form(...)
):
    try:
        entries = json.loads(entries_json)
        # Basic validation
        total_debits = sum(float(e.get('debit', 0) or 0) for e in entries)
        total_credits = sum(float(e.get('credit', 0) or 0) for e in entries)
        if not (0.009 > total_debits - total_credits > -0.009) or total_debits == 0:
            raise ValueError("Journal entry is not balanced or is empty.")
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid entry data: {e}")

    # Enrich entries with account names for the preview
    enriched_entries = []
    for entry in entries:
        account = crud.account.get_account_by_id(db, account_id=int(entry['account_id']), business_id=current_user.business_id)
        if account:
            enriched_entries.append({
                "account_name": account.name,
                "debit": float(entry.get('debit', 0) or 0),
                "credit": float(entry.get('credit', 0) or 0)
            })

    return templates.TemplateResponse("accounting/journal/preview.html", {
        "request": request,
        "user": current_user,
        "user_perms": crud.get_user_permissions(current_user, db),
        "transaction_date": transaction_date,
        "description": description,
        "entries": enriched_entries,
        "total_amount": total_debits,
        "entries_json_for_save": entries_json, # Pass the raw JSON for the final submission
        "title": "Preview Journal Entry"
    })

@router.post("/create", response_class=RedirectResponse)
async def handle_create_journal_entry(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    transaction_date: date = Form(...),
    description: str = Form(...),
    entries_json: str = Form(...)
):
    """Handles the submission of the new journal entry form."""
    try:
        entries = json.loads(entries_json)
        if len(entries) < 2:
            raise ValueError("A journal entry must have at least two lines.")
            
        crud.journal.create_journal_voucher(
            db=db,
            business_id=current_user.business_id,
            branch_id=current_user.selected_branch.id,
            transaction_date=transaction_date,
            description=description,
            entries=entries
        )
        db.commit()
    except ValueError as e:
        db.rollback()
        # Here we can implement the toast notification for the user
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")

    return RedirectResponse(url="/accounting/journal/history", status_code=HTTP_303_SEE_OTHER)


@router.get("/{voucher_id}", response_class=HTMLResponse)
async def get_journal_voucher_detail(
    voucher_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    voucher = db.query(models.JournalVoucher).options(
        joinedload(models.JournalVoucher.ledger_entries).joinedload(models.LedgerEntry.account)
    ).filter(
        models.JournalVoucher.id == voucher_id,
        models.JournalVoucher.business_id == current_user.business_id
    ).first()

    if not voucher:
        raise HTTPException(status_code=404, detail="Journal Voucher not found.")

    return templates.TemplateResponse("accounting/journal/detail.html", {
        "request": request,
        "user": current_user,
        "user_perms": crud.get_user_permissions(current_user, db),
        "voucher": voucher,
        "title": f"Journal Voucher {voucher.voucher_number}"
    })

@router.get("/{voucher_id}", response_class=HTMLResponse)
async def get_journal_voucher_detail(
    voucher_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    # Eagerly load the ledger entries and the account related to each entry
    voucher = db.query(models.JournalVoucher).options(
        joinedload(models.JournalVoucher.ledger_entries).joinedload(models.LedgerEntry.account)
    ).filter(
        models.JournalVoucher.id == voucher_id,
        models.JournalVoucher.business_id == current_user.business_id
    ).first()

    if not voucher:
        raise HTTPException(status_code=404, detail="Journal Voucher not found.")

    # Security check: ensure the voucher belongs to an accessible branch
    if voucher.branch_id not in {b.id for b in current_user.accessible_branches}:
        raise HTTPException(status_code=403, detail="You do not have permission to view this journal entry.")

    user_perms = crud.get_user_permissions(current_user, db)

    return templates.TemplateResponse("accounting/journal/detail.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "voucher": voucher,
        "title": f"Journal Voucher {voucher.voucher_number}"
    })