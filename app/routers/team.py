
from fastapi import APIRouter, Depends, Request, Form, HTTPException, Response, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from pydantic import EmailStr
from .. import crud, models, schemas, security
from ..database import get_db
from ..templating import templates

router = APIRouter(
    prefix="/team",
    tags=["Team Management"],
    dependencies=[Depends(security.get_current_active_user), Depends(security.PermissionChecker(["users:view"]))]
)

@router.post("/users/set-branch/{branch_id}")
async def set_active_branch(branch_id: int, current_user: models.User = Depends(security.get_current_active_user)):
    """
    Sets the selected branch ID in a cookie and triggers a page refresh.
    This version constructs its own Response object to ensure correctness.
    """
    # Ensure the user has access to this branch
    accessible_branch_ids = {b.id for b in current_user.accessible_branches}
    if branch_id not in accessible_branch_ids:
        raise HTTPException(status_code=403, detail="Branch not accessible.")

    response = Response(status_code=status.HTTP_200_OK)
    
    response.set_cookie(key="selected_branch_id", value=str(branch_id), httponly=True, samesite="Lax"  )
    
    response.headers["HX-Refresh"] = "true"
    
    return response




@router.get("/", response_class=HTMLResponse)
async def get_team_management_page(request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(security.get_current_active_user)):
    team_users = crud.get_users_by_business(db, business_id=current_user.business_id)
    branches = crud.get_branches_by_business(db, business_id=current_user.business_id)
    roles = crud.get_roles_by_business(db, business_id=current_user.business_id) 
    user_perms = crud.get_user_permissions(current_user, db)

    return templates.TemplateResponse("team/management.html", {
        "request": request, 
        "user": current_user, 
        "team_users": team_users, 
        "branches": branches, 
        "roles": roles, 
        "user_perms": user_perms, 
        "title": "Team Management"
    })
@router.get("/users/{user_id}/edit", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["users:edit"]))])
async def get_edit_user_modal(user_id: int, request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(security.get_current_active_user)):
    target_user = crud.get_user(db, user_id=user_id)
    if not target_user or target_user.business_id != current_user.business_id:
        raise HTTPException(status_code=404, detail="User not found")
    return templates.TemplateResponse("team/partials/edit_user_modal.html", {"request": request, "target_user": target_user})

@router.put("/users/{user_id}", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["users:edit"]))])
async def handle_update_user(user_id: int, request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(security.get_current_active_user), username: str = Form(...), email: EmailStr = Form(...)):
    target_user = crud.get_user(db, user_id=user_id)
    if not target_user or target_user.business_id != current_user.business_id:
        raise HTTPException(status_code=404, detail="User not found")
    if (username != target_user.username and crud.get_user_by_username_in_business(db, username=username, business_id=current_user.business_id)):
        raise HTTPException(status_code=400, detail="Username already exists.")
    if (email != target_user.email and crud.get_user_by_email_in_business(db, email=email, business_id=current_user.business_id)):
        raise HTTPException(status_code=400, detail="Email already registered.")
    user_update = schemas.UserUpdate(username=username, email=email)
    updated_user = crud.update_user(db, user_id=user_id, user_update=user_update)
    return templates.TemplateResponse("team/partials/user_card_container.html", {"request": request, "team_user": updated_user})

@router.post("/users", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["users:create"]))])
async def create_new_user(
    request: Request, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(security.get_current_active_user), 
    username: str = Form(...), 
    email: EmailStr = Form(...), 
    password: str = Form(...)
):
   
    if crud.get_user_by_username_in_business(db, username=username, business_id=current_user.business_id):
        raise HTTPException(status_code=400, detail=f"Username '{username}' already exists in this business.")
    if crud.get_user_by_email_in_business(db, email=email, business_id=current_user.business_id):
        raise HTTPException(status_code=400, detail=f"Email '{email}' is already registered in this business.")


    user_schema = schemas.UserCreate(username=username, email=email, password=password)
    new_user = crud.create_user(db, user=user_schema, business_id=current_user.business_id)


    try:
        db.commit()
        db.refresh(new_user)
    except Exception as e:
        db.rollback()
      
        raise HTTPException(status_code=500, detail="Failed to save new user to the database.")

    user_perms = crud.get_user_permissions(current_user, db)

    response = templates.TemplateResponse(
        "team/partials/user_card_container.html", 
        {
            "request": request, 
            "team_user": new_user,
            "user_perms": user_perms 
        }
    )

    response.headers["HX-Trigger"] = "userAdded"
    return response

@router.post("/assign-role", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["users:assign-roles"]))])
async def assign_role(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    user_id: int = Form(...),
    branch_id: int = Form(...),
    role_id: int = Form(...)
):

    target_user = crud.get_user(db, user_id)
    if not target_user or target_user.business_id != current_user.business_id:
        raise HTTPException(status_code=404, detail="Target user not found.")

    try:
       
        crud.assign_role_to_user(db, user_id=user_id, branch_id=branch_id, role_id=role_id)

        db.expire(target_user)

        db.commit()

    except Exception as e:
        db.rollback()

        raise HTTPException(status_code=500, detail="Could not assign role due to a database error.")


    target_user_updated = crud.get_user_with_relations(db, username=target_user.username)
    
    user_perms = crud.get_user_permissions(current_user, db)


    return templates.TemplateResponse(
        "team/partials/assign_role_success.html",
        {
            "request": request,
            "team_user": target_user_updated,
            "user_perms": user_perms
        }
    )

@router.delete("/users/{user_id}", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["users:delete"]))])
async def handle_delete_user(user_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(security.get_current_active_user)):
    target_user = crud.get_user(db, user_id)
    if not target_user or target_user.business_id != current_user.business_id:
        raise HTTPException(status_code=404, detail="User not found")
    if target_user.is_superuser:
        raise HTTPException(status_code=403, detail="Cannot delete the main admin account.")
    crud.delete_user(db, user_id=user_id)
    return HTMLResponse(content="", status_code=200)
