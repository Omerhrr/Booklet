
from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from typing import List
from itertools import groupby
from .. import crud, models, schemas, security
from ..database import get_db
from ..templating import templates

router = APIRouter(
    prefix="/settings/roles",
    tags=["Roles"],
    dependencies=[Depends(security.get_current_active_user), Depends(security.PermissionChecker(["roles:view"]))]
)
@router.get("/", response_class=HTMLResponse)
async def get_roles_page(request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(security.get_current_active_user)):
    roles = crud.get_roles_by_business(db, business_id=current_user.business_id)
    

    user_perms = crud.get_user_permissions(current_user, db)

    return templates.TemplateResponse("settings/roles.html", {
        "request": request, 
        "user": current_user, 
        "roles": roles, 
        "user_perms": user_perms, 
        "title": "Manage Roles"
    })

@router.get("/{role_id}/edit", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["roles:edit"]))])
async def get_edit_role_page(role_id: int, request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(security.get_current_active_user)):
    role = crud.get_role(db, role_id=role_id, business_id=current_user.business_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    all_permissions = crud.get_all_permissions(db)
    role_permission_ids = {p.permission_id for p in role.permissions}
    permissions_by_category = {category: list(perms) for category, perms in groupby(all_permissions, key=lambda p: p.category)}
    

    user_perms = crud.get_user_permissions(current_user, db)

    return templates.TemplateResponse("settings/edit_role.html", {
        "request": request, 
        "user": current_user, 
        "role": role, 
        "permissions_by_category": permissions_by_category, 
        "role_permission_ids": role_permission_ids, 
        "user_perms": user_perms, 
        "title": f"Edit Role: {role.name}"
    })
@router.post("/", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["roles:create"]))])
async def handle_create_role(request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(security.get_current_active_user), role_name: str = Form(...), role_description: str = Form("")):
    role_schema = schemas.RoleCreate(name=role_name, description=role_description)
    new_role = crud.create_role(db, role=role_schema, business_id=current_user.business_id)
    return templates.TemplateResponse("settings/partials/role_row.html", {"request": request, "role": new_role})

@router.post("/{role_id}/edit", dependencies=[Depends(security.PermissionChecker(["roles:edit"]))])
async def handle_update_role_permissions(
    role_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):

    form_data = await request.form()
    permission_ids = [int(pid) for pid in form_data.getlist("permission_ids")]

    role = crud.get_role(db, role_id=role_id, business_id=current_user.business_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    try:

        print(f"--- Updating permissions for role ID: {role_id} ---")
        print(f"--- Submitted permission IDs: {permission_ids} ---")
        
        crud.update_role_permissions(db, role_id=role_id, permission_ids=permission_ids)
        print("--- CRUD function executed. Committing... ---")
        
        db.commit()
        print("--- Commit successful. ---")

    except Exception as e:
        db.rollback()

        print("---!!! UPDATE ROLE FAILED !!!---")
        import traceback
        traceback.print_exc()
        print("---------------------------------")
        raise HTTPException(status_code=500, detail="Could not update role permissions.")
    return RedirectResponse(url=f"/settings/roles/{role_id}/edit", status_code=303)