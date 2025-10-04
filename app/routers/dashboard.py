from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from .. import crud, models, security
from ..database import get_db
from ..templating import templates 

router = APIRouter(dependencies=[Depends(security.get_current_active_user)])

@router.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    user_perms = crud.get_user_permissions(current_user, db)
    dashboard_data = crud.reports.get_dashboard_data(db, branch_id=current_user.selected_branch.id, business_id=current_user.business_id)
    
    return templates.TemplateResponse(
        "dashboard/dashboard.html",
        {
            "request": request,
            "user": current_user,
            "user_perms": user_perms, 
            "dashboard_data": dashboard_data,
            "title": "Dashboard"
        }
    )
