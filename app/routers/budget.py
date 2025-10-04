
from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from .. import crud, models, security
from ..database import get_db
from ..templating import templates
from datetime import date
from starlette.status import HTTP_303_SEE_OTHER

router = APIRouter(
    prefix="/budgeting",
    tags=["Budgeting"],
    dependencies=[Depends(security.get_current_active_user), Depends(security.PermissionChecker(["budgeting:view"]))]
)

@router.get("/", response_class=HTMLResponse)
async def get_budget_list_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    """Displays a list of all budgets for the currently selected branch."""
    budgets = crud.budget.get_budgets_by_branch(db, branch_id=current_user.selected_branch.id)
    user_perms = crud.get_user_permissions(current_user, db)
    
    return templates.TemplateResponse("budgeting/list.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "budgets": budgets,
        "title": "Budgets"
    })

@router.get("/new", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["budgeting:create"]))])
async def get_new_budget_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    """Renders the form to create a new budget."""
    revenue_accounts = db.query(models.Account).filter(
        models.Account.business_id == current_user.business_id,
        models.Account.type == models.AccountType.REVENUE
    ).order_by(models.Account.name).all()
    
    expense_accounts = db.query(models.Account).filter(
        models.Account.business_id == current_user.business_id,
        models.Account.type == models.AccountType.EXPENSE
    ).order_by(models.Account.name).all()

    user_perms = crud.get_user_permissions(current_user, db)

    return templates.TemplateResponse("budgeting/create.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "revenue_accounts": revenue_accounts,
        "expense_accounts": expense_accounts,
        "title": "Create New Budget"
    })

@router.post("/new", response_class=RedirectResponse, dependencies=[Depends(security.PermissionChecker(["budgeting:create"]))])
async def handle_create_budget(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    budget_name: str = Form(...),
    start_date: date = Form(...),
    end_date: date = Form(...),
    budget_lines_json: str = Form(...)
):
    """Handles the submission of the new budget form."""
    new_budget = crud.budget.create_budget(
        db=db,
        name=budget_name,
        branch_id=current_user.selected_branch.id,
        start_date=start_date,
        end_date=end_date,
        lines_json=budget_lines_json
    )

    if not new_budget:
        raise HTTPException(status_code=400, detail="Could not create budget. Invalid data provided.")

    return RedirectResponse(url=f"/budgeting/report/{new_budget.id}", status_code=HTTP_303_SEE_OTHER)

@router.get("/{budget_id}", response_class=HTMLResponse)
async def get_budget_detail_page(
    budget_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    """Displays the details of a single, saved budget."""
    budget = crud.budget.get_budget_by_id(db, budget_id=budget_id, branch_id=current_user.selected_branch.id)
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found for this branch.")
        
    user_perms = crud.get_user_permissions(current_user, db)

    revenue_lines = [line for line in budget.lines if line.account.type == models.AccountType.REVENUE]
    expense_lines = [line for line in budget.lines if line.account.type == models.AccountType.EXPENSE]

    return templates.TemplateResponse("budgeting/detail.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "budget": budget,
        "revenue_lines": revenue_lines,
        "expense_lines": expense_lines,
        "title": f"Budget: {budget.name}"
    })

@router.get("/report/{budget_id}", response_class=HTMLResponse)
async def get_budget_report_page(
    budget_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    """Generates and displays the Budget vs. Actuals report."""
    budget = crud.budget.get_budget_by_id(db, budget_id=budget_id, branch_id=current_user.selected_branch.id)
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found for this branch.")

    report_lines = crud.budget.get_budget_vs_actual_report(db, budget=budget)
    
    revenue_lines = [line for line in report_lines if line['account_type'] == models.AccountType.REVENUE]
    expense_lines = [line for line in report_lines if line['account_type'] == models.AccountType.EXPENSE]
    
    user_perms = crud.get_user_permissions(current_user, db)

    return templates.TemplateResponse("budgeting/report.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "budget": budget,
        "revenue_lines": revenue_lines,
        "expense_lines": expense_lines,
        "title": f"Budget Report: {budget.name}"
    })
