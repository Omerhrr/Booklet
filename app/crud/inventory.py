
from sqlalchemy.orm import Session, joinedload, subqueryload
from .. import models, schemas
from sqlalchemy import desc, asc



def get_category(db: Session, category_id: int, branch_id: int): 
    return db.query(models.Category).filter(
        models.Category.id == category_id, 
        models.Category.branch_id == branch_id 
    ).first()

def get_categories_by_branch(db: Session, branch_id: int): 
    return db.query(models.Category).filter(
        models.Category.branch_id == branch_id 
    ).order_by(models.Category.name).all()

def create_category(db: Session, category: schemas.CategoryCreate, business_id: int, branch_id: int): 
    db_category = models.Category(
        **category.model_dump(), 
        business_id=business_id, 
        branch_id=branch_id 
    )
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category



    
def update_category(db: Session, category_id: int, category_update: schemas.CategoryUpdate):
    db_category = db.query(models.Category).filter(models.Category.id == category_id).first()
    if db_category:
        update_data = category_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_category, key, value)
        db.commit()
        db.refresh(db_category)
    return db_category
def delete_category(db: Session, category_id: int):
    db_category = db.query(models.Category).filter(models.Category.id == category_id).first()
    if db_category:
        db.delete(db_category)
        db.commit()
    return db_category

# === Product CRUD ===
def get_product(db: Session, product_id: int, branch_id: int):
    return db.query(models.Product).filter(models.Product.id == product_id, models.Product.branch_id == branch_id).first()
def get_products_by_branch(db: Session, branch_id: int):
    return db.query(models.Product).filter(models.Product.branch_id == branch_id).order_by(models.Product.name).all()

def create_product(db: Session, product: schemas.ProductCreate, branch_id: int):

    db_product = models.Product(
        **product.model_dump(), 
        stock_quantity=product.opening_stock, 
        branch_id=branch_id
    )
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product

def update_product(db: Session, product_id: int, product_update: schemas.ProductUpdate):
    db_product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if db_product:
        update_data = product_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_product, key, value)
        db.commit()
        db.refresh(db_product)
    return db_product

def delete_product(db: Session, product_id: int):
    db_product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if db_product:
        db.delete(db_product)
        db.commit()
    return db_product

def get_products_by_business(db: Session, business_id: int):
    """
    Retrieves all products for a specific business by joining through the branch.
    """
    return db.query(models.Product)\
        .join(models.Branch)\
        .filter(models.Branch.business_id == business_id)\
        .order_by(models.Product.name)\
        .all()


def get_product_with_details(db: Session, product_id: int, business_id: int):
    """
    Gets a single product and eagerly loads its category and stock adjustments.
    """
    return db.query(models.Product).join(models.Branch).options(
        subqueryload(models.Product.stock_adjustments).joinedload(models.StockAdjustment.user),
        joinedload(models.Product.category)
    ).filter(
        models.Product.id == product_id,
        models.Branch.business_id == business_id
    ).first()


# In app/crud/inventory.py

def create_stock_adjustment(db: Session, adjustment: schemas.StockAdjustmentCreate, product_id: int, user_id: int):
    """
    Creates a stock adjustment record AND updates the product's stock quantity.
    This function handles its own transaction commit because it's a self-contained unit of work.
    """

    db_product = db.query(models.Product).filter(models.Product.id == product_id).with_for_update().first()
    
    if not db_product:
        return None

    db_adjustment = models.StockAdjustment(
        product_id=product_id,
        user_id=user_id,
        quantity_change=adjustment.quantity_change,
        reason=adjustment.reason
    )
    db.add(db_adjustment)

  
    db_product.stock_quantity += adjustment.quantity_change

    try:
        db.commit()
        db.refresh(db_product)
        return db_product
    except Exception:
        db.rollback()

        return None


def get_product_by_id(db: Session, product_id: int):
    """
    Gets a single product by its ID.
    """
    return db.query(models.Product).filter(models.Product.id == product_id).first()


def get_stock_adjustments_by_business(db: Session, business_id: int):
    """
    Retrieves all stock adjustment records for a given business,
    eagerly loading the related product and user information.
    """
    return db.query(models.StockAdjustment)\
        .join(models.Product)\
        .join(models.Branch)\
        .filter(models.Branch.business_id == business_id)\
        .options(
            joinedload(models.StockAdjustment.product),
            joinedload(models.StockAdjustment.user)
        )\
        .order_by(desc(models.StockAdjustment.created_at))\
        .all()