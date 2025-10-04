
from fastapi import APIRouter, Depends, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session, joinedload
from pydantic import EmailStr
from datetime import date
from starlette.status import HTTP_303_SEE_OTHER
from typing import Optional, List
from fastapi.encoders import jsonable_encoder
import json

from .. import crud, models, schemas, security
from ..database import get_db
from ..templating import templates

router = APIRouter(
    prefix="/hr",
    tags=["Human Resources"],
    dependencies=[Depends(security.get_current_active_user)]
)

@router.get("/employees", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["hr:view"]))])
async def get_employees_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    # Filter employees by the currently selected branch
    employees = crud.employee.get_employees_by_branch(
        db, 
        branch_id=current_user.selected_branch.id
    )
    user_perms = crud.get_user_permissions(current_user, db)
    return templates.TemplateResponse("hr/employees.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "employees": employees,
        "selected_branch": current_user.selected_branch,
        "title": "Employees"
    })

@router.get("/employees/new", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["hr:create"]))])
async def get_new_employee_form(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    user_perms = crud.get_user_permissions(current_user, db)
    pay_frequencies = [f.value for f in models.PayFrequency]
    return templates.TemplateResponse("hr/new_employee.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "pay_frequencies": pay_frequencies,
        "selected_branch": current_user.selected_branch,
        "title": "Add New Employee"
    })

@router.post("/employees/new", dependencies=[Depends(security.PermissionChecker(["hr:create"]))])
async def handle_create_employee(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    full_name: str = Form(...),
    email: EmailStr = Form(...),
    phone_number: str = Form(None),
    address: str = Form(None),
    hire_date: date = Form(...),
    gross_salary: float = Form(...),
    pay_frequency: models.PayFrequency = Form(...),
    paye_rate: Optional[float] = Form(None),
    pension_employee_rate: Optional[float] = Form(None),
    pension_employer_rate: Optional[float] = Form(None)
):
    # Employee is automatically assigned to the currently active branch
    branch_id = current_user.selected_branch.id

    paye_decimal = paye_rate / 100 if paye_rate is not None else None
    pension_employee_decimal = pension_employee_rate / 100 if pension_employee_rate is not None else None
    pension_employer_decimal = pension_employer_rate / 100 if pension_employer_rate is not None else None
    
    payroll_schema = schemas.PayrollConfigCreate(
        gross_salary=gross_salary, pay_frequency=pay_frequency, paye_rate=paye_decimal,
        pension_employee_rate=pension_employee_decimal, pension_employer_rate=pension_employer_decimal
    )
    employee_schema = schemas.EmployeeCreate(
        full_name=full_name, email=email, phone_number=phone_number, address=address,
        hire_date=hire_date, branch_id=branch_id, payroll_config=payroll_schema
    )
    try:
        crud.employee.create_employee(db=db, employee=employee_schema, business_id=current_user.business_id)
    except Exception as e:
        print(e)
        raise HTTPException(status_code=400, detail="Failed to create employee. An employee with this email may already exist.")
    return RedirectResponse(url="/hr/employees", status_code=HTTP_303_SEE_OTHER)




@router.get("/employees/{employee_id}", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["hr:view"]))])
async def get_employee_detail_page(
    employee_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    employee = crud.employee.get_employee_by_id(db, employee_id=employee_id, business_id=current_user.business_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    if employee.branch_id not in [b.id for b in current_user.accessible_branches]:
        raise HTTPException(status_code=403, detail="You do not have access to this employee.")

    payslips = crud.employee.get_payslips_by_employee(db, employee_id=employee_id)
    ledger_entries_objects = crud.get_employee_ledger(db, employee_id=employee_id, business_id=current_user.business_id)
    ledger_summary = crud.get_employee_ledger_summary(db, employee_id=employee_id, business_id=current_user.business_id)
    

    ledger_entries_json = jsonable_encoder(ledger_entries_objects)
    
    user_perms = crud.get_user_permissions(current_user, db)
    
    return templates.TemplateResponse("hr/employee_detail.html", {
        "request": request, 
        "user": current_user, 
        "user_perms": user_perms,
        "employee": employee,
        "payslips": payslips,
        "ledger_entries_json": ledger_entries_json,
        "ledger_summary": ledger_summary,
        "title": f"Employee: {employee.full_name}"
    })

@router.get("/employees/{employee_id}/edit-info", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["hr:edit"]))])
async def get_edit_employee_info_form(employee_id: int, request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(security.get_current_active_user)):
    employee = crud.employee.get_employee_by_id(db, employee_id=employee_id, business_id=current_user.business_id)
    if not employee: raise HTTPException(status_code=404)
    return templates.TemplateResponse("hr/partials/edit_employee_info.html", {"request": request, "employee": employee})

@router.put("/employees/{employee_id}/edit-info", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["hr:edit"]))])
async def handle_update_employee_info(
    employee_id: int, request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(security.get_current_active_user),
    full_name: str = Form(...), email: EmailStr = Form(...), phone_number: str = Form(None),
    hire_date: date = Form(...), address: str = Form(None)
):
    employee_update = schemas.EmployeeUpdate(full_name=full_name, email=email, phone_number=phone_number, hire_date=hire_date, address=address)
    updated_employee = crud.employee.update_employee(db, employee_id=employee_id, employee_update=employee_update, business_id=current_user.business_id)
    if not updated_employee: raise HTTPException(status_code=404)
    return templates.TemplateResponse("hr/partials/view_employee_info.html", {"request": request, "employee": updated_employee})

@router.get("/employees/{employee_id}/edit-payroll", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["hr:edit"]))])
async def get_edit_payroll_config_form(employee_id: int, request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(security.get_current_active_user)):
    employee = crud.employee.get_employee_by_id(db, employee_id=employee_id, business_id=current_user.business_id)
    if not employee: raise HTTPException(status_code=404)
    pay_frequencies = [f.value for f in models.PayFrequency]
    return templates.TemplateResponse("hr/partials/edit_payroll_config.html", {"request": request, "employee": employee, "pay_frequencies": pay_frequencies})

@router.put("/employees/{employee_id}/edit-payroll", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["hr:edit"]))])
async def handle_update_payroll_config(
    employee_id: int, request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(security.get_current_active_user),
    gross_salary: float = Form(...), pay_frequency: models.PayFrequency = Form(...),
    paye_rate: Optional[float] = Form(None), pension_employee_rate: Optional[float] = Form(None), pension_employer_rate: Optional[float] = Form(None)
):
    payroll_update = schemas.PayrollConfigUpdate(
        gross_salary=gross_salary, pay_frequency=pay_frequency,
        paye_rate=paye_rate / 100 if paye_rate is not None else None,
        pension_employee_rate=pension_employee_rate / 100 if pension_employee_rate is not None else None,
        pension_employer_rate=pension_employer_rate / 100 if pension_employer_rate is not None else None
    )
    updated_employee = crud.employee.update_payroll_config(db, employee_id=employee_id, payroll_update=payroll_update, business_id=current_user.business_id)
    if not updated_employee: raise HTTPException(status_code=404)
    return templates.TemplateResponse("hr/partials/view_payroll_config.html", {"request": request, "employee": updated_employee})

@router.put("/employees/{employee_id}/status", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["hr:edit"]))])
async def handle_update_employee_status(
    employee_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    is_active: bool = Form(...)
):
    updated_employee = crud.employee.update_employee_status(
        db, employee_id=employee_id, is_active=is_active, business_id=current_user.business_id
    )
    if not updated_employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    return templates.TemplateResponse("hr/partials/employee_status_toggle.html", {"request": request, "employee": updated_employee})

@router.get("/payroll/run", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["hr:run_payroll"]))])
async def get_run_payroll_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    # Fetch active employees only from the currently selected branch
    employees_query = db.query(models.Employee).options(joinedload(models.Employee.payroll_config)).filter(
        models.Employee.business_id == current_user.business_id,
        models.Employee.branch_id == current_user.selected_branch.id,
        models.Employee.is_active == True
    )
    employees = employees_query.all()
    employees_json = jsonable_encoder(employees)
    user_perms = crud.get_user_permissions(current_user, db)
    return templates.TemplateResponse("hr/run_payroll.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "employees_data": employees_json,
        "selected_branch": current_user.selected_branch,
        "title": "Run Payroll"
    })

@router.post("/payroll/run", dependencies=[Depends(security.PermissionChecker(["hr:run_payroll"]))])
async def handle_run_payroll(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    pay_period_start: date = Form(...),
    pay_period_end: date = Form(...),
    payroll_data: str = Form(...)
):
    try:
        employees_to_pay = json.loads(payroll_data)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid payroll data format.")

    if not employees_to_pay:
        return RedirectResponse(url="/hr/payroll/run?error=No employees selected", status_code=HTTP_303_SEE_OTHER)

    try:
        with db.begin_nested():
            for emp_data in employees_to_pay:
                # Security check: ensure the employee belongs to the active branch
                employee = crud.employee.get_employee_by_id(db, emp_data['employee_id'], current_user.business_id)
                if not employee or employee.branch_id != current_user.selected_branch.id:
                    raise ValueError(f"Attempted to run payroll for an employee not in the active branch.")

                crud.employee.process_payroll_for_employee(
                    db=db, employee_id=emp_data['employee_id'], business_id=current_user.business_id,
                    pay_period_start=pay_period_start, pay_period_end=pay_period_end,
                    additions=emp_data.get('additions', []), deductions=emp_data.get('deductions', [])
                )
        db.commit()
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")

    return RedirectResponse(url="/hr/payslips", status_code=HTTP_303_SEE_OTHER)

@router.get("/payslips", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["hr:view"]))])
async def get_payslip_history_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    payslips = crud.employee.get_payslips_by_business(db, business_id=current_user.business_id)
    user_perms = crud.get_user_permissions(current_user, db)
    return templates.TemplateResponse("hr/payslip_history.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "payslips": payslips,
        "title": "Payslip History"
    })

@router.get("/payslips/{payslip_id}", response_class=HTMLResponse, dependencies=[Depends(security.PermissionChecker(["hr:view"]))])
async def get_payslip_detail_page(
    payslip_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    payslip = crud.employee.get_payslip_by_id(db, payslip_id=payslip_id, business_id=current_user.business_id)
    if not payslip:
        raise HTTPException(status_code=404, detail="Payslip not found")
    
    user_perms = crud.get_user_permissions(current_user, db)
    
    total_additions = sum(a.amount for a in payslip.additions)
    
    return templates.TemplateResponse("hr/payslip_detail.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "payslip": payslip,
        "total_additions": total_additions,
        "title": f"Payslip for {payslip.employee.full_name}"
    })