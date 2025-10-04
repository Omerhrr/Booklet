# Create new file: app/routers/settings_business.py

from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from .. import crud, models, security
from ..database import get_db
from ..templating import templates
from starlette.status import HTTP_303_SEE_OTHER

router = APIRouter(
    prefix="/settings/business",
    tags=["Settings"],
    dependencies=[Depends(security.get_current_active_user), Depends(security.PermissionChecker(["users:assign-roles"]))] # Admin-level permission
)

@router.get("/", response_class=HTMLResponse)
async def get_business_settings_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    """Renders the page for configuring general business settings, including VAT."""

    user_perms = crud.get_user_permissions(current_user, db)
    
    return templates.TemplateResponse("settings/business_settings.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "business": current_user.business,
        "title": "Business Settings"
    })

@router.post("/", response_class=RedirectResponse)
async def handle_update_business_settings(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    business_name: str = Form(...),
    is_vat_registered: bool = Form(False),
    vat_rate_percent: float = Form(0.0)
):
    """Updates the business settings."""
    business = current_user.business
    
    business.name = business_name
    business.is_vat_registered = is_vat_registered
    business.vat_rate = vat_rate_percent / 100.0 # Convert percentage to decimal
    
    db.add(business)
    db.commit()
    
    return RedirectResponse(url="/settings/business", status_code=HTTP_303_SEE_OTHER)
