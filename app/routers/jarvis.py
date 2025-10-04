
from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from .. import crud, models, security
from ..database import get_db
from ..templating import templates
import json
import google.generativeai as genai
import markdown
from ..ai_providers import get_ai_provider

router = APIRouter(
    prefix="/jarvis",
    tags=["AI Analyst"],
    dependencies=[Depends(security.get_current_active_user)]
)

@router.get("/", response_class=HTMLResponse)
async def get_jarvis_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user)
):
    """
    Renders the main Jarvis chat interface.
    It fetches all business data securely and embeds it in the page.
    """
    branch_id_filter = None
    if not current_user.is_superuser or (current_user.selected_branch and current_user.selected_branch.id != 0):
         branch_id_filter = current_user.selected_branch.id if current_user.selected_branch else None

    business_data = crud.reports.get_business_data_as_json(
        db, 
        business_id=current_user.business_id, 
        branch_id=branch_id_filter
    )
    
    business_data_json_string = json.dumps(business_data)

    return templates.TemplateResponse("jarvis/chat.html", {
        "request": request,
        "user": current_user,
        "user_perms": crud.get_user_permissions(current_user, db),
        "business_data_json": business_data_json_string,
        "title": "Jarvis AI Analyst"
    })



@router.post("/ask", response_class=HTMLResponse)
async def handle_ask_jarvis(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_active_user),
    user_question: str = Form(...),
    business_data_json: str = Form(...)
):
    user_message_html = templates.TemplateResponse("jarvis/partials/user_message.html", {
        "request": request,
        "message": user_question
    }).body.decode('utf-8')

    try:
        # 1. Get business settings
        business = current_user.business
        encrypted_key = business.encrypted_api_key
        provider_name = business.ai_provider

        if not encrypted_key or not provider_name:
            raise ValueError("AI provider or API key is not configured. Please set them in AI Settings.")
        
        api_key = security.decrypt_data(encrypted_key)

        # 2. THE FIX: Get the correct provider dynamically
        ai_provider = get_ai_provider(provider_name)

        # 3. Define the System Prompt (unchanged)
        system_prompt = """
        You are Jarvis, an expert financial and business analyst.
        Your sole purpose is to answer questions based ONLY on the JSON data provided.
        Do not use any external knowledge. Do not browse the internet.
        If the answer cannot be found in the provided JSON, you must state that clearly.
        
        Analyze the following JSON data which contains information about customers, vendors, products, sales, purchases, and expenses for a business.
        
        When providing your answer:
        - Be concise and professional.
        - Use simple Markdown for formatting (e.g., **bold** for emphasis, lists with `-` or `*`).
        - Perform calculations if necessary (e.g., totals, averages).
        - Present lists of items clearly.
        
        Here is the business data:
        """

        # 4. Generate the response using the selected provider
        ai_message_text = await ai_provider.ask(api_key, system_prompt, business_data_json, user_question)
        
        # 5. Convert Markdown to HTML
        ai_message_html = markdown.markdown(ai_message_text, extensions=['fenced_code', 'tables'])

    except (ValueError, ConnectionError) as e:
        ai_message_html = f"<p class='text-red-500'>Configuration Error: {e}</p>"
    except Exception as e:
        print(f"An unexpected error occurred in /ask: {e}")
        ai_message_html = "<p class='text-red-500'>An unexpected error occurred. Please check the server logs.</p>"

    jarvis_response_html = templates.TemplateResponse("jarvis/partials/jarvis_message.html", {
        "request": request,
        "message": ai_message_html
    }).body.decode('utf-8')

    return HTMLResponse(content=user_message_html + jarvis_response_html)