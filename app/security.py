# In: app/security.py

from fastapi import Depends, HTTPException, status, Request, Response
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session, subqueryload
from typing import List, Set
from cryptography.fernet import Fernet

from . import models, crud
from .database import get_db


ENCRYPTION_KEY = Fernet.generate_key()
f = Fernet(ENCRYPTION_KEY)

SECRET_KEY = "K7gJ9mP2qR5tY8vX3wZ6nQ4sA1dF7hJ0kL3pO8rT2yU5iM9nB4vX6cZ3aS8dF1gH"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def encrypt_data(data: str) -> str:
    """Encrypts a string and returns it as a URL-safe string."""
    if not data:
        return ""
    return f.encrypt(data.encode()).decode()

def decrypt_data(encrypted_data: str) -> str:
    """Decrypts a string and returns it."""
    if not encrypted_data:
        return ""
    return f.decrypt(encrypted_data.encode()).decode()

def verify_password(plain_password, hashed_password): return pwd_context.verify(plain_password, hashed_password)
def get_password_hash(password): return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def authenticate_user(db: Session, username: str, password: str):
    """
    Authenticates a user. Uses the SIMPLE get_user_by_username.
    """
    user = crud.get_user_by_username(db, username=username) # Uses the simple function
    if not user or not verify_password(password, user.hashed_password):
        return None # Return None on failure
    return user

async def get_current_user(request: Request, db: Session = Depends(get_db)):
    """
    The dependency that protects our routes.
    Uses the COMPREHENSIVE get_user_with_relations.
    """
    token = request.cookies.get("access_token")
    credentials_exception = HTTPException(
        status_code=status.HTTP_302_FOUND,
        detail="Could not validate credentials",
        headers={"Location": "/login"},
    )
    if not token:
        raise credentials_exception
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:

        raise credentials_exception from None

    user = crud.get_user_with_relations(db, username=username)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(
    request: Request,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    This enhanced dependency attaches the user's accessible branches and
    currently selected branch to the user object for easy access in routes.
    """
    # 1. Determine all branches the user has access to.
    if current_user.is_superuser:
        current_user.accessible_branches = crud.get_branches_by_business(db, business_id=current_user.business_id)
    else:
        # For regular users, accessible branches are those they have a role in.
        current_user.accessible_branches = [assignment.branch for assignment in current_user.roles]

    if not current_user.accessible_branches:
        # This is a critical issue - a user must be associated with at least one branch.
        # In a real app, you might redirect to an error page or log them out.
        raise HTTPException(status_code=403, detail="User is not assigned to any branch.")

    # 2. Determine the currently selected branch.
    selected_branch_id_str = request.cookies.get("selected_branch_id")
    selected_branch = None

    if selected_branch_id_str:
        try:
            selected_branch_id = int(selected_branch_id_str)
            # Find the branch from the user's list of accessible branches.
            selected_branch = next((b for b in current_user.accessible_branches if b.id == selected_branch_id), None)
        except (ValueError, TypeError):
            selected_branch = None

    # 3. If no valid branch is selected (or on first login), set a sensible default.
    if not selected_branch:
        if current_user.is_superuser:
            # For superusers, default to the business's designated default branch.
            selected_branch = next((b for b in current_user.accessible_branches if b.is_default), current_user.accessible_branches[0])
        else:
            # For regular users, default to their first assigned branch.
            selected_branch = current_user.accessible_branches[0]

    # 4. Attach the selected branch to the user object for global use.
    current_user.selected_branch = selected_branch
    
    return current_user


class PermissionChecker:
    def __init__(self, required_permissions: List[str]):
        self.required_permissions = set(required_permissions)

    def __call__(self, user: models.User = Depends(get_current_active_user), db: Session = Depends(get_db)): 
        if user.is_superuser:
            return 
        user_permissions = crud.get_user_permissions(user, db) 
        
        if not self.required_permissions.issubset(user_permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action."
            )
