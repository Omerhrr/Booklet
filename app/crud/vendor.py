from sqlalchemy.orm import Session
from .. import models, schemas



def get_vendor(db: Session, vendor_id: int, business_id: int):
    """
    Gets a single vendor by its ID, ensuring it belongs to the correct business.
    """
    return db.query(models.Vendor).filter(
        models.Vendor.id == vendor_id,
        models.Vendor.business_id == business_id 
    ).first()




def get_vendors_by_branch(db: Session, branch_id: int, business_id: int, skip: int = 0, limit: int = 100):
    """
    Retrieves all vendors for a specific branch within a specific business.
    """
    return db.query(models.Vendor).filter(
        models.Vendor.branch_id == branch_id,
        models.Vendor.business_id == business_id # <-- Add this condition
    ).order_by(models.Vendor.name).offset(skip).limit(limit).all()


def create_vendor(db: Session, vendor: schemas.VendorCreate):
    """
    Creates a new vendor.
    """
    # The vendor schema now includes business_id, so we can pass it directly
    db_vendor = models.Vendor(**vendor.model_dump())
    db.add(db_vendor)
    db.commit()
    db.refresh(db_vendor)
    return db_vendor


def update_vendor(db: Session, vendor_id: int, business_id: int, vendor_update: schemas.VendorUpdate):
    """
    Updates a vendor's details, ensuring it belongs to the correct business.
    """
    db_vendor = get_vendor(db, vendor_id=vendor_id, business_id=business_id) 
    if not db_vendor:
        return None

    update_data = vendor_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_vendor, key, value)

    db.commit()
    db.refresh(db_vendor)
    return db_vendor
    

def delete_vendor(db: Session, vendor_id: int, business_id: int):
    """
    Deletes a vendor, ensuring it belongs to the correct business.
    """
    db_vendor = get_vendor(db, vendor_id=vendor_id, business_id=business_id)
    if db_vendor:
        db.delete(db_vendor)
        db.commit()
        return True
    return False


def get_vendors_by_business(db: Session, business_id: int, skip: int = 0, limit: int = 100):
    """
    Retrieves all vendors for a specific business.
    """
    return db.query(models.Vendor)\
        .filter(models.Vendor.business_id == business_id)\
        .order_by(models.Vendor.name)\
        .offset(skip)\
        .limit(limit)\
        .all()