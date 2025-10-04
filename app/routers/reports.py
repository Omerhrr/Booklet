# In: app/routers/reports.py

from fastapi import APIRouter, Depends, Request, Query, HTTPException, Response, Form
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
from sqlalchemy.orm import Session
from .. import crud, models, security
from ..database import get_db
from ..templating import templates
from datetime import date
from typing import Optional
from starlette.status import HTTP_303_SEE_OTHER
router = APIRouter(
    prefix="/reports",
    tags=["Reports"],
    dependencies=[Depends(security.get_current_active_user)]
)

@router.get("/consolidated-dashboard", response_class=HTMLResponse)
async def get_consolidated_dashboard_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="You do not have permission to view this report.")

    report_data = crud.reports.get_consolidated_dashboard_data(db, business_id=current_user.business_id)
    user_perms = crud.get_user_permissions(current_user, db)

    return templates.TemplateResponse("reports/consolidated_dashboard.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "report_data": report_data,
        "title": "Consolidated Branch Dashboard"
    })

@router.get("/sales", response_class=HTMLResponse)
async def get_sales_report_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    start_date: date = Query(date.today().replace(day=1)),
    end_date: date = Query(date.today()),
    customer_id_str: Optional[str] = Query(None, alias="customer_id"), 
    branch_id: Optional[int] = Query(None)
):
    try:
        customer_id = int(customer_id_str) if customer_id_str else None
    except (ValueError, TypeError):
        customer_id = None

    if branch_id is None and current_user.accessible_branches:
        branch_id = current_user.selected_branch.id
    
    effective_branch_id = None if branch_id == 0 and current_user.is_superuser else branch_id

    invoices, total_sales = crud.reports.get_sales_report(
        db,
        business_id=current_user.business_id,
        start_date=start_date,
        end_date=end_date,
        customer_id=customer_id,
        branch_id=effective_branch_id
    )
    
    customers = crud.get_customers_by_business(db, business_id=current_user.business_id)
    user_perms = crud.get_user_permissions(current_user, db)
    
    return templates.TemplateResponse("reports/sales_report.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "invoices": invoices,
        "total_sales": total_sales,
        "customers": customers,
        "branches": current_user.accessible_branches,
        "filters": {
            "start_date": start_date,
            "end_date": end_date,
            "customer_id": customer_id,
            "branch_id": branch_id
        },
        "title": "Sales Report"
    })


@router.get("/purchase", response_class=HTMLResponse)
async def get_purchase_report_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    start_date: date = Query(date.today().replace(day=1)),
    end_date: date = Query(date.today()),
    vendor_id_str: Optional[str] = Query(None, alias="vendor_id"),
    branch_id: Optional[int] = Query(None)
):
    try:
        vendor_id = int(vendor_id_str) if vendor_id_str else None
    except (ValueError, TypeError):
        vendor_id = None

    if branch_id is None and current_user.accessible_branches:
        branch_id = current_user.selected_branch.id
    
    effective_branch_id = None if branch_id == 0 and current_user.is_superuser else branch_id

    bills, total_purchases = crud.reports.get_purchase_report(
        db,
        business_id=current_user.business_id,
        start_date=start_date,
        end_date=end_date,
        vendor_id=vendor_id,
        branch_id=effective_branch_id
    )
    
    vendors = crud.get_vendors_by_business(db, business_id=current_user.business_id)
    user_perms = crud.get_user_permissions(current_user, db)
    
    return templates.TemplateResponse("reports/purchase_report.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "bills": bills,
        "total_purchases": total_purchases,
        "vendors": vendors,
        "branches": current_user.accessible_branches,
        "filters": {
            "start_date": start_date,
            "end_date": end_date,
            "vendor_id": vendor_id,
            "branch_id": branch_id
        },
        "title": "Purchases Report"
        })

@router.get("/expenses", response_class=HTMLResponse)
async def get_expense_report_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    start_date: date = Query(date.today().replace(day=1)),
    end_date: date = Query(date.today()),
    category: Optional[str] = Query(None),
    branch_id: Optional[int] = Query(None)
):
    if branch_id is None and current_user.accessible_branches:
        branch_id = current_user.selected_branch.id

    effective_branch_id = None if branch_id == 0 and current_user.is_superuser else branch_id

    expenses, total_expenses = crud.reports.get_expense_report(
        db, business_id=current_user.business_id, start_date=start_date, end_date=end_date,
        category=category, branch_id=effective_branch_id
    )
    
    expense_accounts = crud.get_expense_accounts(db, business_id=current_user.business_id)
    user_perms = crud.get_user_permissions(current_user, db)
    
    return templates.TemplateResponse("reports/expense_report.html", {
        "request": request, "user": current_user, "user_perms": user_perms,
        "expenses": expenses, "total_expenses": total_expenses,
        "expense_accounts": expense_accounts, "branches": current_user.accessible_branches,
        "filters": { "start_date": start_date, "end_date": end_date, "category": category, "branch_id": branch_id },
        "title": "Expense Report"
    })


@router.get("/trial-balance", response_class=HTMLResponse)
async def get_trial_balance_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    as_of_date: date = Query(date.today())
):
    report_data = crud.reports.get_trial_balance_data(
        db, 
        business_id=current_user.business_id, 
        branch_id=current_user.selected_branch.id,
        as_of_date=as_of_date
    )
    
    user_perms = crud.get_user_permissions(current_user, db)
    
    return templates.TemplateResponse("reports/trial_balance.html", {
        "request": request, 
        "user": current_user, 
        "user_perms": user_perms,
        "report_data": report_data, 
        "as_of_date": as_of_date,
        "title": "Trial Balance"
    })


@router.get("/export/trial-balance")
async def export_trial_balance_report(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    as_of_date: date = Query(date.today())
):
    lines, _, _ = crud.reports.get_trial_balance_data(
        db, business_id=current_user.business_id, as_of_date=as_of_date
    )

    headers = ["Account", "Type", "Debit", "Credit"]
    data_to_export = [
        [
            line["account_name"],
            line["account_type"],
            line["debit"] if line["debit"] != 0 else '',
            line["credit"] if line["credit"] != 0 else ''
        ] for line in lines
    ]

    excel_buffer = crud.reports.export_to_excel(headers, data_to_export, "Trial Balance")
    
    return StreamingResponse(
        excel_buffer,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f'attachment; filename="trial_balance_{as_of_date}.xlsx"'}
    )



@router.get("/export/sales")
async def export_sales_report(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    start_date: date = Query(date.today().replace(day=1)),
    end_date: date = Query(date.today()),
    customer_id: Optional[int] = Query(None),
    branch_id: Optional[int] = Query(None)
):
    effective_branch_id = None if branch_id == 0 and current_user.is_superuser else branch_id
    invoices, _ = crud.reports.get_sales_report(
        db, business_id=current_user.business_id, start_date=start_date, end_date=end_date,
        customer_id=customer_id, branch_id=effective_branch_id
    )

    headers = ["Date", "Invoice #", "Customer", "Branch", "Amount", "Status"]
    data_to_export = [
        [
            inv.invoice_date.strftime('%Y-%m-%d'),
            inv.invoice_number,
            inv.customer.name if inv.customer else '',
            inv.branch.name if inv.branch else '',
            inv.total_amount,
            inv.status
        ] for inv in invoices
    ]

    excel_buffer = crud.reports.export_to_excel(headers, data_to_export, "Sales Report")
    
    return StreamingResponse(
        excel_buffer,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f'attachment; filename="sales_report_{date.today()}.xlsx"'}
    )

@router.get("/export/purchase")
async def export_purchase_report(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    start_date: date = Query(date.today().replace(day=1)),
    end_date: date = Query(date.today()),
    vendor_id: Optional[int] = Query(None),
    branch_id: Optional[int] = Query(None)
):
    effective_branch_id = None if branch_id == 0 and current_user.is_superuser else branch_id
    bills, _ = crud.reports.get_purchase_report(
        db, business_id=current_user.business_id, start_date=start_date, end_date=end_date,
        vendor_id=vendor_id, branch_id=effective_branch_id
    )

    headers = ["Date", "Bill #", "Vendor", "Branch", "Amount", "Status"]
    data_to_export = [
        [
            bill.bill_date.strftime('%Y-%m-%d'),
            bill.bill_number,
            bill.vendor.name if bill.vendor else '',
            bill.branch.name if bill.branch else '',
            bill.total_amount,
            bill.status
        ] for bill in bills
    ]

    excel_buffer = crud.reports.export_to_excel(headers, data_to_export, "Purchase Report")
    
    return StreamingResponse(
        excel_buffer,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f'attachment; filename="purchase_report_{date.today()}.xlsx"'}
    )

@router.get("/export/expenses")
async def export_expenses_report(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    start_date: date = Query(date.today().replace(day=1)),
    end_date: date = Query(date.today()),
    category: Optional[str] = Query(None),
    branch_id: Optional[int] = Query(None)
):
    effective_branch_id = None if branch_id == 0 and current_user.is_superuser else branch_id
    expenses, _ = crud.reports.get_expense_report(
        db, business_id=current_user.business_id, start_date=start_date, end_date=end_date,
        category=category, branch_id=effective_branch_id
    )

    headers = ["Date", "Category", "Description", "Branch", "Vendor", "Amount"]
    data_to_export = [
        [
            exp.expense_date.strftime('%Y-%m-%d'),
            exp.category,
            exp.description,
            exp.branch.name if exp.branch else '',
            exp.vendor.name if exp.vendor else 'N/A',
            exp.amount
        ] for exp in expenses
    ]

    excel_buffer = crud.reports.export_to_excel(headers, data_to_export, "Expense Report")
    
    return StreamingResponse(
        excel_buffer,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f'attachment; filename="expense_report_{date.today()}.xlsx"'}
    )


@router.get("/aging", response_class=HTMLResponse)
async def get_aging_report_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    as_of_date: date = Query(date.today())
):
    ar_report = crud.reports.get_ar_aging_report(db, branch_id=current_user.selected_branch.id, business_id=current_user.business_id, as_of_date=as_of_date)
    ap_report = crud.reports.get_ap_aging_report(db, branch_id=current_user.selected_branch.id, business_id=current_user.business_id, as_of_date=as_of_date)
    
    user_perms = crud.get_user_permissions(current_user, db)
    
    return templates.TemplateResponse("reports/aging_report.html", {
        "request": request, "user": current_user, "user_perms": user_perms,
        "ar_report": ar_report,
        "ap_report": ap_report,
        "as_of_date": as_of_date,
        "title": "AR/AP Aging Report"
    })



@router.get("/vat-return", response_class=HTMLResponse)
async def get_vat_return_report_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    start_date: date = Query(date.today().replace(day=1)),
    end_date: date = Query(date.today())
):
    # This report only makes sense for VAT-registered businesses
    if not current_user.business.is_vat_registered:
        raise HTTPException(status_code=403, detail="This report is only available for VAT-registered businesses.")

    try:
        report_data = crud.reports.get_vat_report_data(
            db,
            business_id=current_user.business_id,
            branch_id=current_user.selected_branch.id,
            start_date=start_date,
            end_date=end_date
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    user_perms = crud.get_user_permissions(current_user, db)
    
    payment_accounts = crud.banking.get_payment_accounts(db, current_user.business_id, current_user.selected_branch.id)
    
    return templates.TemplateResponse("reports/vat_return_report.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "report_data": report_data,
        "payment_accounts": payment_accounts, # Pass payment accounts
        "filters": { "start_date": start_date, "end_date": end_date },
        "title": "VAT Return Report"
    })


@router.post("/vat-return/pay", response_class=RedirectResponse)
async def handle_vat_payment(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    payment_date: date = Form(...),
    amount_paid: float = Form(...),
    payment_account_id: int = Form(...),
    output_vat_total: float = Form(...),
    input_vat_total: float = Form(...)
):
    """Handles the form submission for recording a VAT payment."""
    try:
        crud.ledger.create_vat_payment_entry(
            db=db,
            business_id=current_user.business_id,
            branch_id=current_user.selected_branch.id,
            payment_date=payment_date,
            amount_paid=amount_paid,
            payment_account_id=payment_account_id,
            output_vat_total=output_vat_total,
            input_vat_total=input_vat_total
        )
        db.commit()
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")

    # Redirect to the cashbook to show the payment has been recorded
    return RedirectResponse(url="/accounting/cashbook", status_code=HTTP_303_SEE_OTHER)

@router.get("/statement/customer/{customer_id}/pdf", response_class=Response)
async def get_customer_statement_pdf(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    start_date: date = Query(...),
    end_date: date = Query(...)
):
    lines, opening_balance, closing_balance, customer = crud.reports.get_account_statement_data(
        db, business_id=current_user.business_id, start_date=start_date, end_date=end_date, customer_id=customer_id
    )

    if not customer:
        return Response("Customer not found", status_code=404)

    context = {
        "request": {},
        "business": current_user.business,
        "target": customer,
        "lines": lines,
        "opening_balance": opening_balance,
        "closing_balance": closing_balance,
        "start_date": start_date,
        "end_date": end_date,
        "statement_type": "Customer"
    }

    pdf_buffer = crud.reports.render_html_to_pdf("reports/pdf/statement_template.html", context, templates)

    return Response(
        pdf_buffer.read(),
        media_type='application/pdf',
        headers={'Content-Disposition': f'inline; filename="statement_{customer.name}_{end_date}.pdf"'}
    )

@router.get("/statement/vendor/{vendor_id}/pdf", response_class=Response)
async def get_vendor_statement_pdf(
    vendor_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    start_date: date = Query(...),
    end_date: date = Query(...)
):
    lines, opening_balance, closing_balance, vendor = crud.reports.get_account_statement_data(
        db, business_id=current_user.business_id, start_date=start_date, end_date=end_date, vendor_id=vendor_id
    )

    if not vendor:
        return Response("Vendor not found", status_code=404)

    context = {
        "request": {},
        "business": current_user.business,
        "target": vendor,
        "lines": lines,
        "opening_balance": opening_balance,
        "closing_balance": closing_balance,
        "start_date": start_date,
        "end_date": end_date,
        "statement_type": "Vendor"
    }

    pdf_buffer = crud.reports.render_html_to_pdf("reports/pdf/statement_template.html", context, templates)

    return Response(
        pdf_buffer.read(),
        media_type='application/pdf',
        headers={'Content-Disposition': f'inline; filename="statement_{vendor.name}_{end_date}.pdf"'}
    )


@router.get("/stock-valuation", response_class=HTMLResponse)
async def get_stock_valuation_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    branch_id: Optional[int] = Query(None)
):
    if branch_id is None and current_user.accessible_branches:
        branch_id = current_user.selected_branch.id
    
    effective_branch_id = None if branch_id == 0 and current_user.is_superuser else branch_id

    lines, grand_total = crud.reports.get_stock_valuation_report(
        db, business_id=current_user.business_id, branch_id=effective_branch_id
    )
    
    user_perms = crud.get_user_permissions(current_user, db)
    
    return templates.TemplateResponse("reports/stock_valuation_report.html", {
        "request": request, "user": current_user, "user_perms": user_perms,
        "lines": lines,
        "grand_total": grand_total,
        "branches": current_user.accessible_branches,
        "filters": { "branch_id": branch_id },
        "title": "Stock Valuation Report"
    })

@router.get("/export/stock-valuation")
async def export_stock_valuation_report(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    branch_id: Optional[int] = Query(None)
):
    effective_branch_id = None if branch_id == 0 and current_user.is_superuser else branch_id
    lines, _ = crud.reports.get_stock_valuation_report(
        db, business_id=current_user.business_id, branch_id=effective_branch_id
    )

    headers = ["Product", "SKU", "Branch", "Category", "Quantity", "Purchase Price", "Total Value"]
    data_to_export = [
        [
            line["product_name"],
            line["sku"],
            line["branch_name"],
            line["category_name"],
            line["stock_quantity"],
            line["purchase_price"],
            line["total_value"]
        ] for line in lines
    ]

    excel_buffer = crud.reports.export_to_excel(headers, data_to_export, "Stock Valuation Report")
    
    return StreamingResponse(
        excel_buffer,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f'attachment; filename="stock_valuation_report_{date.today()}.xlsx"'}
    )
