
from sqlalchemy.orm import Session, joinedload
from .. import models, schemas
from typing import List
def get_role(db: Session, role_id: int, business_id: int):
    return db.query(models.Role).filter(models.Role.id == role_id, models.Role.business_id == business_id).first()

def get_roles(db: Session):
    # Gets all roles, typically for assigning.
    return db.query(models.Role).order_by(models.Role.name).all()

def get_roles_by_business(db: Session, business_id: int):
    # Gets all roles for a specific business, for management.
    return db.query(models.Role).filter(models.Role.business_id == business_id).order_by(models.Role.name).all()

def create_role(db: Session, role: schemas.RoleCreate, business_id: int):
    db_role = models.Role(**role.dict(), business_id=business_id, is_system=False)
    db.add(db_role)
    db.commit()
    db.refresh(db_role)
    return db_role



def create_default_roles_for_business(db: Session, business_id: int):
    """
    Creates a standard set of roles for a new business.
    Returns the created 'Admin' role.
    DOES NOT COMMIT.
    """
    default_roles = [
        {"name": "Admin", "description": "Full administrative access to all settings and branches."},
        {"name": "Branch Manager", "description": "Manages a specific branch's operations."},
        {"name": "Accountant", "description": "Manages financial records and reporting."},
        {"name": "Salesperson", "description": "Creates sales invoices and manages customers."},
        {"name": "Purchasing Officer", "description": "Manages purchase bills and vendors."},
        {"name": "HR/Payroll Officer", "description": "Manages employee data and payroll."},
    ]

    admin_role_object = None
    for role_data in default_roles:
        db_role = models.Role(
            **role_data,
            business_id=business_id,
            is_system=True 
        )
        db.add(db_role)
        if role_data["name"] == "Admin":
            admin_role_object = db_role
            
    return admin_role_object



def get_all_permissions(db: Session):
    return db.query(models.Permission).order_by(models.Permission.category, models.Permission.name).all()



def update_role_permissions(db: Session, role_id: int, permission_ids: List[int]):
    """
    Correctly updates permissions for a role by manually managing the
    association table. This is the robust way to handle this.
    DOES NOT COMMIT.
    """

    role = db.query(models.Role).filter(models.Role.id == role_id).first()
    if not role:
        raise ValueError(f"Role with ID {role_id} not found.")


    db.query(models.RolePermission).filter(models.RolePermission.role_id == role_id).delete()

    for p_id in permission_ids:
        new_association = models.RolePermission(role_id=role_id, permission_id=p_id)
        db.add(new_association)



def assign_role_to_user(db: Session, user_id: int, branch_id: int, role_id: int):
    """
    Adds or updates a UserBranchRole assignment in the session.
    DOES NOT COMMIT.
    """
    assignment = db.query(models.UserBranchRole).filter(
        models.UserBranchRole.user_id == user_id,
        models.UserBranchRole.branch_id == branch_id
    ).first()

    if assignment:
        assignment.role_id = role_id
    else:
        assignment = models.UserBranchRole(user_id=user_id, branch_id=branch_id, role_id=role_id)
        db.add(assignment)

    return assignment
