# Create new file: app/routers/analytics.py

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse
from .. import crud, models, security
from ..database import get_db
from ..templating import templates
from fastapi import Query
from typing import List, Dict, Any
from ..crud import analytics as analytics_crud 
from sqlalchemy.orm import Session
from datetime import date
from dateutil.relativedelta import relativedelta
import json

router = APIRouter(
    prefix="/analytics",
    tags=["Analytics"],
    dependencies=[Depends(security.get_current_active_user)] # Basic dependency for access
)

@router.get("/", response_class=HTMLResponse)
async def get_analytics_hub_page(request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(security.get_current_active_user)):
    user_perms = crud.get_user_permissions(current_user, db)
    return templates.TemplateResponse("analytics/hub.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "title": "Analytics Studio"
    })

@router.get("/comparison", response_class=HTMLResponse)
async def get_comparison_tool_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    metrics: List[str] = Query(None),
    dimension: str = Query("month"),
    start_date: date = Query(date.today() - relativedelta(months=5)),
    end_date: date = Query(date.today())
):
    user_perms = crud.get_user_permissions(current_user, db)
    
    chart_data = None
    if metrics:
        try:
            # For non-admins, force the query to their branch. For admins, allow cross-branch.
            branch_filter = current_user.selected_branch.id if not current_user.is_superuser else None
            
            chart_data = analytics_crud.get_comparison_data(
                db=db,
                business_id=current_user.business_id,
                branch_id=branch_filter,
                metrics=metrics,
                dimension=dimension,
                start_date=start_date,
                end_date=end_date
            )
        except ValueError as e:
            # Handle cases like unsupported dimensions gracefully
            print(f"Analytics Error: {e}") # Log the error
            chart_data = {"error": str(e)}

    return templates.TemplateResponse("analytics/comparison_tool.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "title": "Comparison Tool",
        "metric_options": ["Total Sales", "Gross Profit", "Net Profit", "Total Expenses"],
        "dimension_options": ["Month", "Branch"], # Only showing supported dimensions
        "filters": {
            "metrics": metrics or [],
            "dimension": dimension,
            "start_date": start_date,
            "end_date": end_date
        },
        "chart_data": chart_data
    })

@router.get("/financial-health", response_class=HTMLResponse)
async def get_financial_health_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    as_of_date: date = Query(date.today())
):
    """
    Renders the Financial Health Scorecard page with key ratios and trends.
    """
    user_perms = crud.get_user_permissions(current_user, db)
    
    # For non-admins, force the query to their branch. For admins, use the selected branch.
    branch_id = current_user.selected_branch.id
    
    ratio_data = analytics_crud.get_financial_ratios(
        db=db,
        business_id=current_user.business_id,
        branch_id=branch_id,
        as_of_date=as_of_date
    )

    return templates.TemplateResponse("analytics/financial_health.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "title": "Financial Health Scorecard",
        "as_of_date": as_of_date,
        "ratio_data": ratio_data
    })

@router.get("/deep-dive", response_class=HTMLResponse)
async def get_deep_dive_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    metric: str = Query("Total Expenses"),
    start_date: date = Query(date.today().replace(day=1)),
    end_date: date = Query(date.today())
):
    """
    Renders the Deep Dive Analyzer page with a sunburst chart.
    """
    user_perms = crud.get_user_permissions(current_user, db)
    branch_id = current_user.selected_branch.id
    
    breakdown_data = analytics_crud.get_metric_breakdown(
        db=db,
        business_id=current_user.business_id,
        branch_id=branch_id,
        metric=metric,
        start_date=start_date,
        end_date=end_date
    )

    return templates.TemplateResponse("analytics/deep_dive.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "title": f"Deep Dive: {metric}",
        "metric_options": ["Total Expenses", "Total Sales"],
        "filters": {
            "metric": metric,
            "start_date": start_date,
            "end_date": end_date
        },
        "breakdown_data": breakdown_data
    })






@router.get("/cash-flow-forecast", response_class=HTMLResponse)
async def get_cash_flow_forecast_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    """
    Renders the initial Cash Flow Forecaster page.
    """
    user_perms = crud.get_user_permissions(current_user, db)
    
    # Generate initial forecast with no scenarios
    initial_forecast_data = analytics_crud.get_cash_flow_forecast(
        db=db,
        business_id=current_user.business_id,
        branch_id=current_user.selected_branch.id,
        scenarios=[]
    )
    
    return templates.TemplateResponse("analytics/cash_flow_forecaster.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "title": "Cash Flow Forecaster",
        "forecast_data": initial_forecast_data
    })

@router.post("/cash-flow-forecast/update", response_class=HTMLResponse)
async def handle_update_forecast(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    scenarios_json: str = Form(...)
):
    """
    Receives scenario data from the frontend, recalculates the forecast,
    and returns just the updated chart data.
    """
    try:
        scenarios = json.loads(scenarios_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid scenario format.")

    updated_forecast_data = analytics_crud.get_cash_flow_forecast(
        db=db,
        business_id=current_user.business_id,
        branch_id=current_user.selected_branch.id,
        scenarios=scenarios
    )
    
    # Return only the chart partial, which HTMX will swap into the page
    return templates.TemplateResponse("analytics/partials/forecast_chart.html", {
        "request": request,
        "forecast_data": updated_forecast_data
    })
