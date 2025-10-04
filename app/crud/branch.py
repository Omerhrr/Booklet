
from sqlalchemy.orm import Session
from .. import models, schemas


def create_branch(db: Session, branch: schemas.BranchCreate, business_id: int, is_default: bool = False):
    """
    Adds a new Branch object to the session.
    DOES NOT COMMIT.
    """
    db_branch = models.Branch(**branch.dict(), business_id=business_id, is_default=is_default)
    db.add(db_branch)
    db.commit()

    db.refresh(db_branch)
    return db_branch




def get_branches_by_business(db: Session, business_id: int):
    return db.query(models.Branch).filter(models.Branch.business_id == business_id).order_by(models.Branch.name).all()

def get_branch(db: Session, branch_id: int):
    return db.query(models.Branch).filter(models.Branch.id == branch_id).first()


def update_branch(db: Session, branch_id: int, branch_update: schemas.BranchUpdate):
    db_branch = get_branch(db, branch_id=branch_id)
    if not db_branch:
        return None

    update_data = branch_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_branch, key, value)

    db.add(db_branch)
    db.commit()
    db.refresh(db_branch)
    return db_branch



def delete_branch(db: Session, branch_id: int, business_id: int) -> bool:
    """
    Deletes a branch and all its associated data.
    Returns True on success, False on failure (e.g., branch not found or is default).
    """
    branch = db.query(models.Branch).filter(
        models.Branch.id == branch_id,
        models.Branch.business_id == business_id
    ).first()

    if not branch:
        return False # Branch not found
    
    if branch.is_default:
        # Add a safety check to prevent deleting the last remaining branch
        branch_count = db.query(models.Branch).filter(models.Branch.business_id == business_id).count()
        if branch_count <= 1:
            return False # Cannot delete the last/default branch

    # SQLAlchemy's cascade will handle deleting related records
    db.delete(branch)
    db.commit()
    return True