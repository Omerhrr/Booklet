from fastapi import APIRouter, Depends, HTTPException, status, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from datetime import timedelta


from .. import crud, models, schemas, security
from ..database import get_db
from ..templating import templates
from starlette.status import HTTP_303_SEE_OTHER 

router = APIRouter(tags=["Authentication"])



@router.get("/", response_class=HTMLResponse)
async def get_root(request: Request):
    return templates.TemplateResponse("auth/login.html", {"request": request, "title": "Login"})

@router.get("/login", response_class=HTMLResponse)
async def get_login_page(request: Request):
    return templates.TemplateResponse("auth/login.html", {"request": request, "title": "Login"})

@router.get("/signup", response_class=HTMLResponse)
async def get_signup_page(request: Request):
    return templates.TemplateResponse("auth/signup.html", {"request": request, "title": "Sign Up"})



@router.post("/signup")
async def handle_signup(
    db: Session = Depends(get_db),
    business_name: str = Form(...),
    email: str = Form(...),
    username: str = Form(...),
    password: str = Form(...)
):
    """
    Handles the entire business and user creation process as a single
    transactional unit of work. This version correctly creates roles
    per business.
    """

    if crud.get_user_by_username(db, username=username):
        raise HTTPException(status_code=400, detail="Username already exists.")
    if crud.get_user_by_email(db, email=email):
        raise HTTPException(status_code=400, detail="Email already registered.")

    try:

        business = crud.create_business(db, name=business_name)
        db.flush() 
        admin_role = crud.create_default_roles_for_business(db, business_id=business.id)
        if not admin_role:

            raise Exception("Failed to create the default Admin role.")
        db.flush() 

        user_schema = schemas.UserCreate(username=username, email=email, password=password)
        user = crud.create_user(db, user=user_schema, business_id=business.id, is_superuser=True)
        db.flush() 
        branch_schema = schemas.BranchCreate(name="Main Branch", currency="USD")
        branch = crud.create_branch(db, branch=branch_schema, business_id=business.id, is_default=True)
        db.flush() 
        crud.assign_role_to_user(db, user_id=user.id, branch_id=branch.id, role_id=admin_role.id)

        crud.create_default_chart_of_accounts(db, business_id=business.id)

        db.commit()

    except Exception as e:
        db.rollback()

        raise HTTPException(status_code=500, detail="Could not create account due to a server error.")


    user_with_relations = crud.get_user_with_relations(db, username=user.username)
    if not user_with_relations:
        raise HTTPException(status_code=404, detail="Could not log in user after creation.")

    access_token = security.create_access_token(data={"sub": user_with_relations.username})


    response = Response(status_code=200) 
    response.set_cookie(key="access_token", value=access_token, httponly=True, samesite="Lax" )
    

    response.headers["HX-Redirect"] = "/dashboard"
    
    return response
















@router.post("/token")
async def login_for_access_token(
    request: Request,
    db: Session = Depends(get_db), 
    username: str = Form(...), 
    password: str = Form(...),

):
    """
    Handles login. On success, sets a cookie and sends an HX-Redirect
    header to tell the browser to go to the dashboard.
    """
    user = security.authenticate_user(db, username=username, password=password)
    if not user:

        return templates.TemplateResponse("auth/partials/login_error.html", {
            "request": request
        })

    access_token_expires = timedelta(minutes=security.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={"sub": user.username}, 
        expires_delta=access_token_expires
    )
    
    response = Response(status_code=200)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=int(access_token_expires.total_seconds( )),
        samesite="Lax",
    )

    response.headers["HX-Redirect"] = "/dashboard"
    
    return response


@router.get("/logout")
async def logout(response: Response):
    response = RedirectResponse(url="/login")
    response.delete_cookie(key="access_token")
    return response