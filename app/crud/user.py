
from sqlalchemy.orm import Session, subqueryload, joinedload
from typing import Set
from .. import models, schemas, security, crud 

def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()


def get_users_by_business(db: Session, business_id: int):
    return db.query(models.User).filter(models.User.business_id == business_id).all()


def get_user_by_username(db: Session, username: str):
    """
    Gets a user by username for authentication purposes.
    This is a SIMPLE query and should NOT load any relationships.
    """
    return db.query(models.User).filter(models.User.username == username).first()



def create_user(db: Session, user: schemas.UserCreate, business_id: int, is_superuser: bool = False):
    """
    Adds a new User object to the session. Hashes the password.
    DOES NOT COMMIT.
    """
    hashed_password = security.get_password_hash(user.password)
    db_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password,
        business_id=business_id,
        is_superuser=is_superuser,
    )
    db.add(db_user)
    return db_user





def update_user(db: Session, user_id: int, user_update: schemas.UserUpdate):
    db_user = get_user(db, user_id)
    if db_user:
        update_data = user_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_user, key, value)
        db.commit()
        db.refresh(db_user)
    return db_user

def delete_user(db: Session, user_id: int):
    db_user = get_user(db, user_id)
    if db_user:
        db.delete(db_user)
        db.commit()
    return db_user

def get_user_by_username_in_business(db: Session, username: str, business_id: int):
    return db.query(models.User).filter(models.User.username == username, models.User.business_id == business_id).first()

def get_user_by_email_in_business(db: Session, email: str, business_id: int):
    return db.query(models.User).filter(models.User.email == email, models.User.business_id == business_id).first()

def get_user_permissions(user: models.User, db: Session) -> Set[str]: # <-- Add db: Session
    """
    Gets all permission names for a given user.
    If the user is a superuser, it returns all permissions in the system.
    Otherwise, it aggregates permissions from their assigned roles.
    """
    if user.is_superuser:
        # Superuser gets all permissions that exist in the database.
        return crud.get_all_permission_names(db)

    # For regular users, collect permissions from their roles.
    perms = set()
    if user.roles:
        for ubr in user.roles: # ubr = UserBranchRole
            if ubr.role and ubr.role.permissions:
                for p in ubr.role.permissions: # p = RolePermission
                    if p.permission:
                        perms.add(p.permission.name)
    return perms

def get_user_with_relations(db: Session, username: str):
    """
    Gets a user by username and eagerly loads all necessary relationships
    for an active session (business, roles, permissions).
    """
    return (
        db.query(models.User)
        .filter(models.User.username == username)
        .options(
            joinedload(models.User.business),
            subqueryload(models.User.roles)
            .joinedload(models.UserBranchRole.role)
            .subqueryload(models.Role.permissions)
            .joinedload(models.RolePermission.permission),
        )
        .first()
    )

