# Create new file: app/routers/onboarding.py

from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from .. import crud, models, security, schemas
from ..database import get_db
from ..templating import templates
from ..ai_providers import get_ai_provider
from fastapi.encoders import jsonable_encoder
import json
from datetime import date

router = APIRouter(
    prefix="/onboarding",
    tags=["Onboarding"],
    dependencies=[Depends(security.get_current_active_user)]
)

@router.get("/data-importer", response_class=HTMLResponse)
async def get_data_importer_page(request: Request,  db: Session = Depends(get_db), current_user: models.User = Depends(security.get_current_active_user)):
    """Renders the main page for the AI-powered data importer."""
    user_perms = crud.get_user_permissions(current_user, db)
    return templates.TemplateResponse("onboarding/data_importer.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "title": "AI Data Importer"
    })

@router.post("/data-importer/analyze", response_class=HTMLResponse)
async def handle_analyze_data(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    data_type: str = Form(...),
    raw_data: str = Form(...)
):
    """
    Takes raw text data, sends it to the AI for parsing, and returns a
    confirmation form with the structured data.
    """
    # Define the target schema for the AI based on the user's selection
    target_schema = ""
    if data_type == "customers":
        target_schema = schemas.CustomerCreate.model_json_schema()
    elif data_type == "vendors":
        target_schema = schemas.VendorCreate.model_json_schema()
    elif data_type == "products":
        target_schema = schemas.ProductCreate.model_json_schema()
    else:
        raise HTTPException(status_code=400, detail="Invalid data type specified.")

    system_prompt = f"""
    You are an expert data migration assistant named 'Setter'. Your task is to convert raw, unstructured user-pasted data into a clean JSON array of objects.
    The final JSON must strictly adhere to this target JSON Schema:
    {json.dumps(target_schema, indent=2)}

    - Analyze the user's raw data and intelligently map their columns to the fields in the schema.
    - The user's data might have different header names (e.g., 'Client Name' should map to 'name').
    - Handle common data formats like tab-separated, comma-separated, or just copied from an Excel sheet.
    - For 'customers' and 'vendors', the 'branch_id' and 'business_id' will be added later, so you can omit them.
    - For 'products', ensure 'purchase_price', 'sales_price', and 'opening_stock' are numbers.
    - Your final output must ONLY be the JSON array. Do not include any explanations, apologies, or surrounding text like ```json.
    """

    try:
        business = current_user.business
        api_key = security.decrypt_data(business.encrypted_api_key)
        ai_provider = get_ai_provider(business.ai_provider)
        
        # Get the structured JSON string from the AI
        json_string = await ai_provider.ask(api_key, system_prompt, "", raw_data)
        
        # Validate and parse the AI's response
        parsed_data = json.loads(json_string)
        if not isinstance(parsed_data, list):
            raise ValueError("AI did not return a valid JSON array.")

    except Exception as e:
        # If AI fails, return an error message to the user
        return templates.TemplateResponse("onboarding/partials/importer_error.html", {
            "request": request,
            "error_message": f"The AI failed to process the data. Please check the format or try again. (Error: {e})"
        })

    # If successful, render the confirmation step
    return templates.TemplateResponse("onboarding/partials/importer_confirmation.html", {
        "request": request,
        "data_type": data_type,
        "structured_data": parsed_data,
        "structured_data_json": json.dumps(parsed_data) # Pass for final submission
    })


@router.post("/data-importer/import", response_class=HTMLResponse)
async def handle_import_data(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    data_type: str = Form(...),
    structured_data_json: str = Form(...)
):
    """
    Receives the confirmed, structured JSON data and saves it to the database.
    """
    try:
        records = json.loads(structured_data_json)
        if not isinstance(records, list):
            raise ValueError("Data is not a valid list of records.")
    except (json.JSONDecodeError, ValueError) as e:
        return templates.TemplateResponse("onboarding/partials/importer_error.html", {
            "request": request,
            "error_message": f"Invalid data format received. Please try the analysis again. (Error: {e})"
        })

    imported_count = 0
    error_count = 0
    
    # Get the current branch and business IDs once
    branch_id = current_user.selected_branch.id
    business_id = current_user.business_id

    try:
        with db.begin_nested(): # Use a transaction
            for record in records:
                try:
                    if data_type == "customers":
                        # Add required IDs to the record before creating
                        record['branch_id'] = branch_id
                        record['business_id'] = business_id
                        customer_schema = schemas.CustomerCreate(**record)
                        crud.create_customer(db, customer=customer_schema)
                    
                    elif data_type == "vendors":
                        record['branch_id'] = branch_id
                        record['business_id'] = business_id
                        vendor_schema = schemas.VendorCreate(**record)
                        crud.create_vendor(db, vendor=vendor_schema)

                    elif data_type == "products":
                        # Products are created per branch, business is inferred
                        record['branch_id'] = branch_id
                        product_schema = schemas.ProductCreate(**record)
                        crud.create_product(db, product=product_schema, branch_id=branch_id)
                    
                    imported_count += 1
                except Exception as e:
                    # This allows us to skip bad records and continue importing good ones
                    print(f"Skipping record due to error: {record} - Error: {e}")
                    error_count += 1
        db.commit()
    except Exception as e:
        db.rollback()
        return templates.TemplateResponse("onboarding/partials/importer_error.html", {
            "request": request,
            "error_message": f"A database error occurred during import. No data was saved. (Error: {e})"
        })

    # Render a success message
    return templates.TemplateResponse("onboarding/partials/importer_success.html", {
        "request": request,
        "data_type": data_type,
        "imported_count": imported_count,
        "error_count": error_count
    })


@router.get("/opening-balances", response_class=HTMLResponse)
async def get_opening_balances_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    """Renders the page for users to input their opening balances."""
    chart_of_accounts = crud.get_chart_of_accounts(db, business_id=current_user.business_id)
    
    # IMPORTANT: Use jsonable_encoder to prevent serialization errors in the template
    accounts_json = jsonable_encoder(chart_of_accounts)
    
    user_perms = crud.get_user_permissions(current_user, db=request.state.db)
    return templates.TemplateResponse("onboarding/opening_balances.html", {
        "request": request,
        "user": current_user,
        "user_perms": user_perms,
        "accounts_json": accounts_json, # Pass the JSON-safe data
        "title": "Enter Opening Balances"
    })

@router.post("/opening-balances", response_class=HTMLResponse)
async def handle_save_opening_balances(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    go_live_date: date = Form(...),
    description: str = Form("Opening Balance Journal Entry"),
    entries_json: str = Form(...)
):
    """Saves the opening balances as a single journal voucher."""
    try:
        entries = json.loads(entries_json)
        if len(entries) < 2:
            raise ValueError("An opening balance entry must have at least two lines.")
            
        # Use the existing, robust journal creation function
        voucher = crud.journal.create_journal_voucher(
            db=db,
            business_id=current_user.business_id,
            branch_id=current_user.selected_branch.id, # Balances are for the primary branch
            transaction_date=go_live_date,
            description=description,
            entries=entries
        )
        db.commit()
    except ValueError as e:
        db.rollback()
        # In a real scenario, you'd return an error partial here
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")

    # Return a success message
    return templates.TemplateResponse("onboarding/partials/balances_success.html", {
        "request": request,
        "voucher_id": voucher.id,
        "voucher_number": voucher.voucher_number
    })