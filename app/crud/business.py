from sqlalchemy.orm import Session
from .. import models, schemas


def create_business(db: Session, name: str, plan: str = "premium"):
    """
    Adds a new Business object to the session.
    DOES NOT COMMIT.
    """
    db_business = models.Business(name=name, plan=plan)
    db.add(db_business)
    return db_business
