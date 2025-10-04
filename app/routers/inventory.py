
from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from .. import crud, models, schemas, security
from ..database import get_db
from ..templating import templates
from typing import Set, List, Optional
from sqlalchemy import desc, asc
router = APIRouter(
    prefix="/inventory",
    tags=["Inventory"],
    dependencies=[Depends(security.get_current_active_user), Depends(security.PermissionChecker(["inventory:view"]))]
)

# === Categories Routes (unchanged) ===
@router.get("/categories", response_class=HTMLResponse)
async def get_categories_page(request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(security.get_current_active_user)):
    categories = crud.get_categories_by_branch(db, branch_id=current_user.selected_branch.id)
    user_perms = crud.get_user_permissions(current_user, db)
    return templates.TemplateResponse("inventory/categories.html", {"request": request, "user": current_user, "categories": categories, "user_perms": user_perms, "title": "Product Categories"})

@router.post("/categories", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["inventory:create"]))])
async def handle_create_category(request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(security.get_current_active_user), name: str = Form(...), description: str = Form("")):
    category_schema = schemas.CategoryCreate(name=name, description=description)
    new_category = crud.create_category(db, category=category_schema,branch_id=current_user.selected_branch.id,business_id=current_user.business_id)
    user_perms = crud.get_user_permissions(current_user, db)
    return templates.TemplateResponse("inventory/partials/category_row.html", {"request": request, "category": new_category, "user_perms": user_perms})

@router.get("/categories/{category_id}/row", response_class=HTMLResponse)
async def get_category_row(category_id: int, request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(security.get_current_active_user)):
    category = crud.get_category(db, category_id=category_id, branch_id=current_user.selected_branch.id)
    if not category: raise HTTPException(status_code=404)
    user_perms = crud.get_user_permissions(current_user, db)
    return templates.TemplateResponse("inventory/partials/category_row.html", {"request": request, "category": category, "user_perms": user_perms})

@router.get("/categories/{category_id}/edit", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["inventory:edit"]))])
async def get_edit_category_form(category_id: int, request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(security.get_current_active_user)):
    category = crud.get_category(db, category_id=category_id, branch_id=current_user.selected_branch.id)
    if not category: raise HTTPException(status_code=404)
    return templates.TemplateResponse("inventory/partials/category_row_edit.html", {"request": request, "category": category})

@router.put("/categories/{category_id}", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["inventory:edit"]))])
async def handle_update_category(category_id: int, request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(security.get_current_active_user), name: str = Form(...), description: str = Form("")):
    category = crud.get_category(db, category_id=category_id, branch_id=current_user.selected_branch.id)
    if not category: raise HTTPException(status_code=404)
    category_update = schemas.CategoryUpdate(name=name, description=description)
    updated_category = crud.update_category(db, category_id=category_id, category_update=category_update)
    user_perms = crud.get_user_permissions(current_user, db)
    return templates.TemplateResponse("inventory/partials/category_row.html", {"request": request, "category": updated_category, "user_perms": user_perms})

@router.delete("/categories/{category_id}", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["inventory:delete"]))])
async def handle_delete_category(category_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(security.get_current_active_user)):
    category = crud.get_category(db, category_id=category_id, branch_id=current_user.selected_branch.id)
    if not category: raise HTTPException(status_code=404)
    if category.products: raise HTTPException(status_code=400, detail="Cannot delete category with associated products.")
    crud.delete_category(db, category_id=category_id)
    return HTMLResponse(content="", status_code=200)

# === Products Routes (Now Branch-Aware) ===
@router.get("/products", response_class=HTMLResponse)
async def get_products_page(request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(security.get_current_active_user)):
    # Simplified: Get products for the currently selected branch
    products = crud.get_products_by_branch(db, branch_id=current_user.selected_branch.id)
    categories = crud.get_categories_by_branch(db, branch_id=current_user.selected_branch.id)
    user_perms = crud.get_user_permissions(current_user, db)
    return templates.TemplateResponse("inventory/products.html", {
        "request": request, 
        "user": current_user, 
        "products": products, 
        "categories": categories, 
        "user_perms": user_perms, 
        "selected_branch": current_user.selected_branch,
        "title": "Products"
    })


@router.post("/products", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["inventory:create"]))])
async def handle_create_product(request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(security.get_current_active_user), name: str = Form(...), sku: str = Form(None), purchase_price: float = Form(...), sales_price: float = Form(...), opening_stock: int = Form(...), category_id: int = Form(...), unit: Optional[str] = Form(None)):
    # Create product in the currently selected branch
    branch_id = current_user.selected_branch.id
    product_schema = schemas.ProductCreate(name=name, sku=sku, purchase_price=purchase_price, sales_price=sales_price, opening_stock=opening_stock, category_id=category_id, unit=unit)
    new_product = crud.create_product(db, product=product_schema, branch_id=branch_id)
    user_perms = crud.get_user_permissions(current_user, db)
    return templates.TemplateResponse("inventory/partials/product_row.html", {"request": request, "product": new_product, "user_perms": user_perms})

@router.delete("/products/{product_id}", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["inventory:delete"]))])
async def handle_delete_product(product_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(security.get_current_active_user)):
    # Ensure product belongs to the selected branch before deleting
    product = crud.get_product(db, product_id=product_id, branch_id=current_user.selected_branch.id)
    if not product: raise HTTPException(status_code=404, detail="Product not found in this branch.")
    crud.delete_product(db, product_id=product_id)
    return HTMLResponse(content="", status_code=200)

@router.get("/products/{product_id}/edit", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["inventory:edit"]))])
async def get_edit_product_form(product_id: int, request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(security.get_current_active_user)):
    product = crud.get_product(db, product_id=product_id, branch_id=current_user.selected_branch.id)
    if not product: raise HTTPException(status_code=404, detail="Product not found in this branch.")
    categories = crud.get_categories_by_branch(db, branch_id=current_user.selected_branch.id)
    return templates.TemplateResponse("inventory/partials/product_row_edit.html", {"request": request, "product": product, "categories": categories})

@router.put("/products/{product_id}", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["inventory:edit"]))])
async def handle_update_product(product_id: int, request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(security.get_current_active_user), name: str = Form(...), sku: str = Form(None), purchase_price: float = Form(...), sales_price: float = Form(...), category_id: int = Form(...), unit: Optional[str] = Form(None)):
    product = crud.get_product(db, product_id=product_id, branch_id=current_user.selected_branch.id)
    if not product: raise HTTPException(status_code=404, detail="Product not found in this branch.")
    product_update = schemas.ProductUpdate(name=name, sku=sku, purchase_price=purchase_price, sales_price=sales_price, category_id=category_id, unit=unit)
    updated_product = crud.update_product(db, product_id=product_id, product_update=product_update)
    user_perms = crud.get_user_permissions(current_user, db)
    return templates.TemplateResponse("inventory/partials/product_row.html", {"request": request, "product": updated_product, "user_perms": user_perms})

@router.get("/products/{product_id}/row", response_class=HTMLResponse)
async def get_product_row(product_id: int, request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(security.get_current_active_user)):
    product = crud.get_product(db, product_id=product_id, branch_id=current_user.selected_branch.id)
    if not product: raise HTTPException(status_code=404, detail="Product not found in this branch.")
    user_perms = crud.get_user_permissions(current_user, db)
    return templates.TemplateResponse("inventory/partials/product_row.html", {"request": request, "product": product, "user_perms": user_perms})

# --- Stock Adjustment Routes (Now Branch-Aware) ---

@router.get("/adjustments", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["inventory:view"]))])
async def get_stock_adjustments_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    adjustments = crud.get_stock_adjustments_by_business(db, business_id=current_user.business_id)
    user_perms = crud.get_user_permissions(current_user, db)
    return templates.TemplateResponse("inventory/stock_adjustments.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "adjustments": adjustments,
        "title": "Stock Adjustment History"
    })

@router.post("/products/{product_id}/adjust-stock", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["inventory:adjust_stock"]))])
async def handle_stock_adjustment(
    product_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    quantity_change: int = Form(...),
    reason: str = Form(...)
):
    # Verify the product belongs to the active branch before adjusting
    product_to_adjust = crud.get_product(db, product_id=product_id, branch_id=current_user.selected_branch.id)
    if not product_to_adjust:
        raise HTTPException(status_code=404, detail="Product not found in the active branch.")

    adjustment_schema = schemas.StockAdjustmentCreate(quantity_change=quantity_change, reason=reason)
    updated_product = crud.create_stock_adjustment(db, adjustment=adjustment_schema, product_id=product_id, user_id=current_user.id)
    
    if not updated_product:
        raise HTTPException(status_code=500, detail="Failed to save stock adjustment.")

    user_perms = crud.get_user_permissions(current_user, db)
    return templates.TemplateResponse(
        "inventory/partials/product_row.html", 
        {"request": request, "product": updated_product, "user_perms": user_perms}
    )

@router.get("/products/{product_id}/view", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["inventory:view"]))])
async def get_product_detail_page(
    product_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    product = crud.get_product_with_details(db, product_id=product_id, business_id=current_user.business_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    # Security check: ensure the product's branch is one the user can access
    if product.branch_id not in [b.id for b in current_user.accessible_branches]:
        raise HTTPException(status_code=403, detail="You do not have access to this product's branch.")

    user_perms = crud.get_user_permissions(current_user, db)
    return templates.TemplateResponse("inventory/product_detail.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "product": product,
        "title": f"Product: {product.name}"
    })

@router.get("/products/{product_id}/adjust-stock-form", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["inventory:adjust_stock"]))])
async def get_adjust_stock_form(
    product_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    product = crud.get_product(db, product_id=product_id, branch_id=current_user.selected_branch.id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found in this branch.")
    
    return templates.TemplateResponse(
        "inventory/partials/product_row_adjust_stock.html",
        {"request": request, "product": product}
    )
