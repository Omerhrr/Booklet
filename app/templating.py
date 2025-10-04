
from fastapi import Request
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy.orm import Session

from . import crud 
from . import models

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(Path(BASE_DIR, "templates")))

templates.env.globals['get_user_permissions'] = crud.get_user_permissions


def inject_user(request: Request):
    if "user" in request.scope:
        return {"user": request.scope["user"]}
    return {}

templates.context_processors.append(inject_user)
