# app/main.py
from fastapi import FastAPI, Request, Depends
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session, registry
from jose import JWTError, jwt

from .database import engine, Base, get_db
from . import models
registry().configure()

from . import crud, security, schemas

from .routers import auth, settings_business,  dashboard, branches, customers, team, roles, inventory, vendors, accounting, purchases, sales, expenses, hr, reports, budget, other_income, banking, jarvis, settings_ai, journal, onboarding, analytics


Base.metadata.create_all(bind=engine)

app = FastAPI()

@app.on_event("startup")
def seed_permissions():
    db = next(get_db())
    all_permissions = [
        {"name": "users:view", "category": "Users"}, 
        {"name": "users:create", "category": "Users"},
        {"name": "users:edit", "category": "Users"}, 
        {"name": "users:delete", "category": "Users"},
        {"name": "users:assign-roles", "category": "Users"},
        {"name": "roles:view", "category": "Roles"}, 
        {"name": "roles:create", "category": "Roles"},
        {"name": "roles:edit", "category": "Roles"},
        {"name": "roles:delete", "category": "Roles"},
        {"name": "branches:view", "category": "Branches"},
        {"name": "branches:create", "category": "Branches"},
        {"name": "branches:edit", "category": "Branches"}, 
        {"name": "branches:delete", "category": "Branches"},
        {"name": "customers:view", "category": "Customers"}, 
        {"name": "customers:create", "category": "Customers"},
        {"name": "customers:edit", "category": "Customers"}, 
        {"name": "customers:delete", "category": "Customers"},
        {"name": "vendors:view", "category": "Vendors"}, 
        {"name": "vendors:create", "category": "Vendors"},
        {"name": "vendors:edit", "category": "Vendors"}, 
        {"name": "vendors:delete", "category": "Vendors"},
        {"name": "inventory:view", "category": "Inventory"},
        {"name": "inventory:create", "category": "Inventory"},
        {"name": "inventory:edit", "category": "Inventory"},
        {"name": "inventory:delete", "category": "Inventory"},
        {"name": "inventory:adjust_stock", "category": "Inventory"},
        {"name": "purchases:view", "category": "Purchases"},
        {"name": "purchases:create", "category": "Purchases"},
        {"name": "purchases:edit", "category": "Purchases"},
        {"name": "purchases:delete", "category": "Purchases"},
        {"name": "purchases:create_debit_note", "category": "Purchases"},
        {"name": "sales:view", "category": "Sales"},
        {"name": "sales:create", "category": "Sales"},
        {"name": "sales:edit", "category": "Sales"},
        {"name": "sales:delete", "category": "Sales"},
        {"name": "sales:create_credit_note", "category": "Sales"},
        {"name": "expenses:view", "category": "Expenses"},
        {"name": "expenses:create", "category": "Expenses"},
        {"name": "expenses:edit", "category": "Expenses"},
        {"name": "expenses:delete", "category": "Expenses"},
        {"name": "accounting:view", "category": "Accounting"},
        {"name": "accounting:create", "category": "Accounting"},
        {"name": "accounting:edit", "category": "Accounting"},
        {"name": "accounting:delete", "category": "Accounting"},
        {"name": "hr:view", "category": "HR"},
        {"name": "hr:create", "category": "HR"},
        {"name": "hr:edit", "category": "HR"},
        {"name": "hr:delete", "category": "HR"},
        {"name": "hr:run_payroll", "category": "HR"},
        {"name": "budgeting:view", "category": "Budgeting"},
        {"name": "budgeting:create", "category": "Budgeting"},
        {"name": "budgeting:edit", "category": "Budgeting"},
        {"name": "budgeting:delete", "category": "Budgeting"},
    ]

    existing_permissions_count = db.query(models.Permission).count()
    if existing_permissions_count < len(all_permissions):
        print(f"--- Found {existing_permissions_count} permissions, re-seeding {len(all_permissions)} total. ---")

        existing_perm_names = {p.name for p in db.query(models.Permission.name).all()}
        for perm_data in all_permissions:
            if perm_data["name"] not in existing_perm_names:
                db.add(models.Permission(**perm_data))
        db.commit()
        print(f"--- {len(all_permissions) - len(existing_perm_names)} new permissions have been seeded. ---")
    else:
        print("--- Permissions already exist, skipping seed. ---")
    db.close()


app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(auth.router)
app.include_router(settings_business.router)
app.include_router(accounting.router)
app.include_router(purchases.router) 
app.include_router(dashboard.router)
app.include_router(branches.router)
app.include_router(customers.router)
app.include_router(team.router)
app.include_router(roles.router)
app.include_router(inventory.router)
app.include_router(vendors.router)
app.include_router(sales.router)
app.include_router(expenses.router)
app.include_router(hr.router)
app.include_router(reports.router)
app.include_router(budget.router) 
app.include_router(other_income.router)
app.include_router(banking.router)
app.include_router(jarvis.router)
app.include_router(settings_ai.router)
app.include_router(journal.router)
app.include_router(onboarding.router)
app.include_router(analytics.router)

