
from sqlalchemy.orm import Session, joinedload
from .. import models, schemas
from typing import Set, List

def get_all_permissions(db: Session):
    return db.query(models.Permission).order_by(models.Permission.category, models.Permission.name).all()

def get_all_permission_names(db: Session) -> Set[str]: # <-- NEW FUNCTION
    """
    Efficiently fetches the names of all defined permissions.
    """
    return {p.name for p in db.query(models.Permission.name).all()}


