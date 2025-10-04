# Create new file: app/crud/analytics.py

from sqlalchemy.orm import Session
from sqlalchemy import func, case
from sqlalchemy.sql.expression import extract
from .. import models, crud
from datetime import date, timedelta
from typing import List, Dict, Any
from dateutil.relativedelta import relativedelta
import numpy as np
from sklearn.linear_model import LinearRegression
def get_comparison_data(
    db: Session,
    business_id: int,
    branch_id: int, # Will be used to filter data for non-admins
    metrics: List[str],
    dimension: str,
    start_date: date,
    end_date: date
) -> Dict[str, Any]:
    """
    Dynamically builds and executes a query to compare various metrics
    across a specified dimension.
    """
    
    # 1. Define how to calculate each metric from the Ledger
    metric_definitions = {
        "Total Sales": func.sum(case(
            (models.Account.name == 'Sales Revenue', models.LedgerEntry.credit - models.LedgerEntry.debit),
            else_=0
        )),
        "Gross Profit": func.sum(case(
            (models.Account.type == models.AccountType.REVENUE, models.LedgerEntry.credit - models.LedgerEntry.debit),
            (models.Account.name == 'Cost of Goods Sold', -(models.LedgerEntry.debit - models.LedgerEntry.credit)),
            else_=0
        )),
        "Net Profit": func.sum(case(
            (models.Account.type == models.AccountType.REVENUE, models.LedgerEntry.credit - models.LedgerEntry.debit),
            (models.Account.type == models.AccountType.EXPENSE, -(models.LedgerEntry.debit - models.LedgerEntry.credit)),
            else_=0
        )),
        "Total Expenses": func.sum(case(
            (models.Account.type == models.AccountType.EXPENSE, models.LedgerEntry.debit - models.LedgerEntry.credit),
            else_=0
        )),
    }

    # 2. Select the calculations requested by the user
    selected_metrics = {key: metric_definitions[key].label(key) for key in metrics if key in metric_definitions}
    if not selected_metrics:
        return None

    # 3. Define the dimension for grouping
    query = db.query(*selected_metrics.values())
    
    dimension_column = None
    if dimension == "month":
        dimension_column = func.strftime('%Y-%m', models.LedgerEntry.transaction_date).label("dimension")
    elif dimension == "branch":
        dimension_column = models.Branch.name.label("dimension")
        query = query.join(models.Branch, models.LedgerEntry.branch_id == models.Branch.id)
    elif dimension == "product_category":
        # This is more complex, requires joining through items and products
        # For now, we'll focus on the first two dimensions
        pass # Placeholder for future enhancement

    if dimension_column is None:
        raise ValueError("Unsupported dimension")

    query = query.add_column(dimension_column)

    # 4. Apply standard filters
    query = query.join(models.Account, models.LedgerEntry.account_id == models.Account.id)\
                 .filter(models.Account.business_id == business_id)\
                 .filter(models.LedgerEntry.transaction_date.between(start_date, end_date))

    # IMPORTANT: Apply branch permission filter if not a superuser
    if branch_id is not None:
        query = query.filter(models.LedgerEntry.branch_id == branch_id)

    # 5. Group by the selected dimension and order it
    query = query.group_by(dimension_column).order_by(dimension_column)

    # 6. Execute the query
    results = query.all()

    # 7. Format the data for ECharts
    if not results:
        return {"categories": [], "series": []}

    categories = [row.dimension for row in results]
    series = []
    for metric_name in selected_metrics.keys():
        series.append({
            "name": metric_name,
            "type": 'bar', # Or 'line', can be configured later
            "data": [getattr(row, metric_name) or 0 for row in results]
        })

    return {"categories": categories, "series": series}


def get_financial_ratios(db: Session, business_id: int, branch_id: int, as_of_date: date) -> Dict[str, Any]:
    """
    Calculates key financial ratios for a specific date and their trends over the last 6 months.
    """
    
    def calculate_ratios_for_period(start_date: date, end_date: date):
        pnl_data = crud.ledger.get_profit_and_loss_data(db, business_id, start_date, end_date, branch_id)
        bs_data = crud.ledger.get_balance_sheet_data(db, business_id, end_date, branch_id)

        total_revenue = pnl_data.get("total_revenue", 0.0)
        gross_profit = pnl_data.get("gross_profit", 0.0)
        net_profit = pnl_data.get("net_profit", 0.0)
        
        # For the Current Ratio, we need to identify current assets and liabilities.
        # For simplicity now, we'll consider all assets/liabilities as current. This can be refined later.
        current_assets = bs_data.get("total_assets", 0.0)
        current_liabilities = bs_data.get("total_liabilities", 0.0)

        # Calculate Ratios
        gross_profit_margin = (gross_profit / total_revenue * 100) if total_revenue else 0
        net_profit_margin = (net_profit / total_revenue * 100) if total_revenue else 0
        current_ratio = (current_assets / current_liabilities) if current_liabilities else 0
        
        return {
            "gross_profit_margin": gross_profit_margin,
            "net_profit_margin": net_profit_margin,
            "current_ratio": current_ratio,
        }

    # Calculate current ratios
    start_of_year = as_of_date.replace(month=1, day=1)
    current_ratios = calculate_ratios_for_period(start_of_year, as_of_date)

    # Calculate trend data for the last 6 months
    trend_labels = []
    gpm_trend, npm_trend, cr_trend = [], [], []

    for i in range(5, -1, -1):
        month_end_date = as_of_date - relativedelta(months=i)
        month_start_date = month_end_date.replace(day=1)
        
        trend_labels.append(month_end_date.strftime('%b'))
        
        # We calculate YTD ratios for each month-end to see the trend
        ytd_start = month_end_date.replace(month=1, day=1)
        monthly_ratios = calculate_ratios_for_period(ytd_start, month_end_date)
        
        gpm_trend.append(round(monthly_ratios["gross_profit_margin"], 2))
        npm_trend.append(round(monthly_ratios["net_profit_margin"], 2))
        cr_trend.append(round(monthly_ratios["current_ratio"], 2))

    return {
        "current": current_ratios,
        "trends": {
            "labels": trend_labels,
            "gross_profit_margin": gpm_trend,
            "net_profit_margin": npm_trend,
            "current_ratio": cr_trend,
        }
    }




def get_cash_flow_forecast(
    db: Session, 
    business_id: int, 
    branch_id: int, 
    scenarios: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Generates a cash flow forecast using linear regression on historical data
    and applying user-defined 'what-if' scenarios.
    """
    # 1. Get historical daily balances for all cash/bank accounts
    today = date.today()
    start_date_hist = today - relativedelta(months=6)
    
    payment_accounts = crud.banking.get_payment_accounts(db, business_id, branch_id)
    if not payment_accounts:
        return {"labels": [], "historical": [], "forecast": []}
    
    account_ids = [acc.id for acc in payment_accounts]

    # Query to get daily net change in cash
    daily_changes = db.query(
        models.LedgerEntry.transaction_date,
        func.sum(models.LedgerEntry.debit - models.LedgerEntry.credit).label('net_change')
    ).filter(
        models.LedgerEntry.account_id.in_(account_ids),
        models.LedgerEntry.branch_id == branch_id,
        models.LedgerEntry.transaction_date.between(start_date_hist, today)
    ).group_by(models.LedgerEntry.transaction_date).order_by(models.LedgerEntry.transaction_date).all()

    # Calculate running balance for historical data
    opening_balance = db.query(func.sum(models.LedgerEntry.debit - models.LedgerEntry.credit)).filter(
        models.LedgerEntry.account_id.in_(account_ids),
        models.LedgerEntry.branch_id == branch_id,
        models.LedgerEntry.transaction_date < start_date_hist
    ).scalar() or 0.0

    balance = opening_balance
    historical_balances = {}
    for d in daily_changes:
        balance += d.net_change
        historical_balances[d.transaction_date] = balance

    # Fill in missing days with the previous day's balance
    running_date = start_date_hist
    last_balance = opening_balance
    processed_historical = []
    labels = []
    while running_date <= today:
        labels.append(running_date.strftime('%Y-%m-%d'))
        last_balance = historical_balances.get(running_date, last_balance)
        processed_historical.append(round(last_balance, 2))
        running_date += timedelta(days=1)

    # 2. Simple Linear Regression Model
    X = np.array(range(len(processed_historical))).reshape(-1, 1)
    y = np.array(processed_historical)
    model = LinearRegression()
    model.fit(X, y)

    # 3. Project future balances
    forecast_days = 90
    future_X = np.array(range(len(processed_historical), len(processed_historical) + forecast_days)).reshape(-1, 1)
    base_forecast = model.predict(future_X)

    # 4. Apply 'what-if' scenarios
    adjusted_forecast = []
    daily_scenario_impact = 0
    for scenario in scenarios:
        if scenario.get('type') == 'expense':
            daily_scenario_impact -= float(scenario.get('amount', 0)) / 30.44 # Avg days in month
        elif scenario.get('type') == 'income':
            daily_scenario_impact += float(scenario.get('amount', 0)) / 30.44

    for i, forecast_val in enumerate(base_forecast):
        adjusted_val = forecast_val + (daily_scenario_impact * (i + 1))
        adjusted_forecast.append(round(adjusted_val, 2))
        if i == 0:
            # The first day of forecast continues from the last historical day
            labels.append((today + timedelta(days=1)).strftime('%Y-%m-%d'))
        else:
            labels.append((today + timedelta(days=i + 1)).strftime('%Y-%m-%d'))

    return {
        "labels": labels,
        "historical": processed_historical,
        "forecast": adjusted_forecast
    }


def get_metric_breakdown(db: Session, business_id: int, branch_id: int, metric: str, start_date: date, end_date: date) -> List[Dict[str, Any]]:
    """
    Generates a hierarchical breakdown of a given metric for use in sunburst or treemap charts.
    Example: Expenses -> Category -> Individual Expense
    """
    results = []
    
    if metric == "Total Expenses":
        # Level 1: Group by Expense Category
        expenses_by_category = db.query(
            models.Expense.category,
            func.sum(models.Expense.amount).label('total_amount')
        ).filter(
            models.Expense.business_id == business_id,
            models.Expense.expense_date.between(start_date, end_date)
        )
        if branch_id:
            expenses_by_category = expenses_by_category.filter(models.Expense.branch_id == branch_id)
            
        expenses_by_category = expenses_by_category.group_by(models.Expense.category).all()

        for category_name, category_total in expenses_by_category:
            category_node = {
                "name": category_name,
                "value": category_total,
                "children": []
            }
            
            # Level 2: Get individual expenses for this category
            individual_expenses = db.query(models.Expense).filter(
                models.Expense.business_id == business_id,
                models.Expense.expense_date.between(start_date, end_date),
                models.Expense.category == category_name
            )
            if branch_id:
                individual_expenses = individual_expenses.filter(models.Expense.branch_id == branch_id)
            
            for expense in individual_expenses.all():
                category_node["children"].append({
                    "name": expense.description[:30] + '...' if len(expense.description) > 30 else expense.description,
                    "value": expense.amount
                })
            results.append(category_node)

    elif metric == "Total Sales":
        # Level 1: Group by Product Category
        sales_by_category = db.query(
            models.Category.name,
            func.sum(models.SalesInvoiceItem.price * models.SalesInvoiceItem.quantity).label('total_revenue')
        ).join(models.SalesInvoiceItem, models.SalesInvoice.id == models.SalesInvoiceItem.sales_invoice_id)\
         .join(models.Product, models.Product.id == models.SalesInvoiceItem.product_id)\
         .join(models.Category, models.Category.id == models.Product.category_id)\
         .filter(
            models.SalesInvoice.business_id == business_id,
            models.SalesInvoice.invoice_date.between(start_date, end_date)
        )
        if branch_id:
            sales_by_category = sales_by_category.filter(models.SalesInvoice.branch_id == branch_id)
            
        sales_by_category = sales_by_category.group_by(models.Category.name).all()

        for category_name, category_total in sales_by_category:
            category_node = {
                "name": category_name,
                "value": category_total,
                "children": []
            }
            
            # Level 2: Get individual products for this category
            sales_by_product = db.query(
                models.Product.name,
                func.sum(models.SalesInvoiceItem.price * models.SalesInvoiceItem.quantity).label('product_total')
            ).join(models.SalesInvoiceItem, models.SalesInvoice.id == models.SalesInvoiceItem.sales_invoice_id)\
             .join(models.Product, models.Product.id == models.SalesInvoiceItem.product_id)\
             .join(models.Category, models.Category.id == models.Product.category_id)\
             .filter(
                models.SalesInvoice.business_id == business_id,
                models.SalesInvoice.invoice_date.between(start_date, end_date),
                models.Category.name == category_name
            )
            if branch_id:
                sales_by_product = sales_by_product.filter(models.SalesInvoice.branch_id == branch_id)
            
            sales_by_product = sales_by_product.group_by(models.Product.name).all()

            for product_name, product_total in sales_by_product:
                category_node["children"].append({
                    "name": product_name,
                    "value": product_total
                })
            results.append(category_node)
            
    return results
