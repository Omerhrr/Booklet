
from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from .. import crud, models, security
from ..database import get_db
from ..templating import templates
from starlette.status import HTTP_303_SEE_OTHER

router = APIRouter(
    prefix="/settings/ai",
    tags=["Settings"],
    dependencies=[Depends(security.get_current_active_user), Depends(security.PermissionChecker(["users:assign-roles"]))] # Re-using a high-level permission for admins
)

@router.get("/", response_class=HTMLResponse)
async def get_ai_settings_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    """Renders the page for configuring the AI provider and API key."""
    user_perms = crud.get_user_permissions(current_user, db)
    
    # Decrypt key only for display purposes (e.g., showing the first few chars)
    decrypted_key = ""
    if current_user.business.encrypted_api_key:
        try:
            decrypted_key = security.decrypt_data(current_user.business.encrypted_api_key)
        except Exception:
            decrypted_key = "Error decrypting key. Please re-enter."

    return templates.TemplateResponse("settings/ai_settings.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "business": current_user.business,
        "decrypted_key": decrypted_key, # Pass the decrypted key to the template
        "title": "AI Settings"
    })

@router.post("/", response_class=RedirectResponse)
async def handle_update_ai_settings(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    ai_provider: str = Form(...),
    api_key: str = Form(...)
):
    """Encrypts and saves the AI provider and API key for the business."""
    business = current_user.business
    
    business.ai_provider = ai_provider
    business.encrypted_api_key = security.encrypt_data(api_key)
    
    db.add(business)
    db.commit()
    
    return RedirectResponse(url="/settings/ai", status_code=HTTP_303_SEE_OTHER)
