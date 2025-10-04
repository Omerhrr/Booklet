
from sqlalchemy.orm import Session
from .. import models, schemas


def get_customers_by_branch(db: Session, branch_id: int, business_id: int, skip: int = 0, limit: int = 100):
    """
    Retrieves all customer for a specific branch within a specific business.
    """
    return db.query(models.Customer).filter(
        models.Customer.branch_id == branch_id,
        models.Customer.business_id == business_id # <-- Add this condition
    ).order_by(models.Customer.name).offset(skip).limit(limit).all()



def create_customer(db: Session, customer: schemas.CustomerCreate):
    """
    Creates a new customer.
    """
    # The customer schema now includes business_id, so we can pass it directly
    db_customer = models.Customer(**customer.model_dump())
    db.add(db_customer)
    db.commit()
    db.refresh(db_customer)
    return db_customer



def get_customer(db: Session, customer_id: int, business_id: int):
    """
    Gets a single customer by its ID, ensuring it belongs to the correct business.
    """
    return db.query(models.Customer).filter(
        models.Customer.id == customer_id,
        models.Customer.business_id == business_id 
    ).first()



def update_customer(db: Session, customer_id: int, customer_update: schemas.CustomerUpdate, business_id: int):
    """
    Updates a customer's details, ensuring it belongs to the correct business.
    """
    db_customer = get_customer(db, customer_id=customer_id, business_id=business_id) 
    if not db_customer:
        return None

    update_data = customer_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_customer, key, value)

    db.commit()
    db.refresh(db_customer)
    return db_customer



def delete_customer(db: Session, customer_id: int, business_id: int):
    """
    Deletes a customer, ensuring it belongs to the correct business.
    """
    db_customer = get_customer(db, customer_id=customer_id, business_id=business_id)
    if db_customer:
        db.delete(db_customer)
        db.commit()
        return True
    return False


def get_customers_by_business(db: Session, business_id: int, skip: int = 0, limit: int = 100):
    """
    Retrieves all customers for a specific business.
    """
    return db.query(models.Customer)\
        .filter(models.Customer.business_id == business_id)\
        .order_by(models.Customer.name)\
        .offset(skip)\
        .limit(limit)\
        .all()