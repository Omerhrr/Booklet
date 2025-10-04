
from fastapi import APIRouter, Depends, Request, Form, HTTPException, Response
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from .. import crud, models, schemas, security
from ..database import get_db
from ..templating import templates 
import json

router = APIRouter(
    prefix="/settings/branches",
    tags=["Branches"],
    dependencies=[Depends(security.get_current_active_user), Depends(security.PermissionChecker(["branches:view"]))]
)

@router.get("/", response_class=HTMLResponse)
async def get_branches_page(request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(security.get_current_active_user)):
    branches = crud.get_branches_by_business(db, business_id=current_user.business_id)
    business_plan = current_user.business.plan
    can_add_branch = (business_plan == "premium" and len(branches) < 10) or business_plan == "enterprise"

    user_perms = crud.get_user_permissions(current_user, db)

    return templates.TemplateResponse("settings/branches.html", {
        "request": request, 
        "user": current_user, 
        "branches": branches, 
        "can_add_branch": can_add_branch, 
        "user_perms": user_perms, 
        "title": "Manage Branches"
    })
@router.post("/", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["branches:create"]))])
async def handle_create_branch(request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(security.get_current_active_user), branch_name: str = Form(...), branch_currency: str = Form(...)):
    branches = crud.get_branches_by_business(db, business_id=current_user.business_id)
    business_plan = current_user.business.plan
    if business_plan == "basic":
        raise HTTPException(status_code=403, detail="Your 'basic' plan does not allow creating new branches.")
    if business_plan == "premium" and len(branches) >= 10:
        raise HTTPException(status_code=403, detail="You have reached the 10-branch limit for the 'premium' plan.")

    existing_branch = db.query(models.Branch).filter(
        models.Branch.business_id == current_user.business_id,
        models.Branch.name == branch_name
    ).first()
    
    if existing_branch:
        # Use the toast notification for a clean error
        response = Response(status_code=400)
        toast_event = {"show-toast": {"message": f"A branch named '{branch_name}' already exists.", "type": "error"}}
        response.headers["HX-Trigger"] = json.dumps(toast_event)
        return response
    branch_schema = schemas.BranchCreate(name=branch_name, currency=branch_currency)
    new_branch = crud.create_branch(db, branch=branch_schema, business_id=current_user.business_id)
    
    return templates.TemplateResponse("settings/partials/branch_row.html", {"request": request, "branch": new_branch})



@router.delete("/{branch_id}", status_code=200, dependencies=[Depends(security.PermissionChecker(["branches:delete"]))])
async def handle_delete_branch(branch_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(security.get_current_active_user)):
    success = crud.delete_branch(db, branch_id=branch_id, business_id=current_user.business_id)
    
    if not success:
        # Use the toast notification for a clean error message
        response = Response(status_code=400)
        toast_event = {
            "show-toast": {
                "message": "Cannot delete this branch. It might be your only branch or the default.",
                "type": "error"
            }
        }
        response.headers["HX-Trigger"] = json.dumps(toast_event)
        return response
        
    # On success, HTMX will remove the row from the table. Return an empty 200 OK.
    return Response(status_code=200)

@router.get("/{branch_id}/edit", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["branches:edit"]))])
async def get_edit_branch_form(branch_id: int, request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(security.get_current_active_user)):
    branch = crud.get_branch(db, branch_id=branch_id)
    if not branch or branch.business_id != current_user.business_id:
        raise HTTPException(status_code=404, detail="Branch not found")
    return templates.TemplateResponse("settings/partials/branch_row_edit.html", {"request": request, "branch": branch})


@router.get("/{branch_id}/row", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["branches:view"]))])
async def get_branch_row(branch_id: int, request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(security.get_current_active_user)):
    """
    Returns a single, non-editable branch row. Used for cancelling an edit.
    """
    branch = crud.get_branch(db, branch_id=branch_id)
    if not branch or branch.business_id != current_user.business_id:
        raise HTTPException(status_code=404, detail="Branch not found")
    

@router.put("/{branch_id}", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["branches:edit"]))])
async def handle_update_branch(branch_id: int, request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(security.get_current_active_user), branch_name: str = Form(...), branch_currency: str = Form(...)):
    branch = crud.get_branch(db, branch_id=branch_id)
    if not branch or branch.business_id != current_user.business_id:
        raise HTTPException(status_code=404, detail="Branch not found")
    branch_update = schemas.BranchUpdate(name=branch_name, currency=branch_currency)
    updated_branch = crud.update_branch(db, branch_id=branch_id, branch_update=branch_update)
    return templates.TemplateResponse("settings/partials/branch_row.html", {"request": request, "branch": updated_branch})
