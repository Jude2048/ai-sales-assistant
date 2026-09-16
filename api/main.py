import os
from urllib.parse import urlencode
from fastapi import FastAPI
from api.webhooks.instagram import router as instagram_router
from fastapi.responses import HTMLResponse, RedirectResponse
from api.webhooks.whatsapp import router as whatsapp_router
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from pymongo import MongoClient
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from shared.mongo import (
    create_lead,
    create_conversation,
    create_message,
    get_lead,
    get_conversation,
    messages_collection,
)

import json
    

app = FastAPI(title="AI Sales Assistant")

app.include_router(instagram_router, prefix="/webhooks")
app.include_router(whatsapp_router, prefix="/webhooks")

mongo_client = MongoClient(os.getenv("MONGODB_URI"))
db = mongo_client["ai_sales_assistant"]
google_tokens = db["google_tokens"] 

@app.get("/")
async def root():
    return {"status": "ok"}

@app.get("/auth/google/callback")
async def google_callback(code: str | None = None):
    if not code:
        return {"error": "Missing authorization code"}

    data = urlencode({
        "code": code,
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
        "redirect_uri": os.getenv("GOOGLE_REDIRECT_URI"),
        "grant_type": "authorization_code",
    }).encode()

    request = Request(
        "https://oauth2.googleapis.com/token",
        data=data,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    with urlopen(request) as response:
        tokens = json.loads(response.read())
        refresh_token = tokens.get("refresh_token")

        if refresh_token:
            google_tokens.update_one(
            {"provider": "gmail"},
            {
             "$set": {
                "provider": "gmail",
                "refresh_token": refresh_token,
                }
            },
            upsert=True,
        )   

    return {
        "status": "Google OAuth successful",
    "refresh_token_saved": bool(refresh_token),
    }

@app.get("/auth/google")
async def google_login():
    params = {
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "redirect_uri": os.getenv("GOOGLE_REDIRECT_URI"),
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/gmail.readonly",
        "access_type": "offline",
        "prompt": "consent",
    }

    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)

    return RedirectResponse(url)

@app.get("/debug/gmail/inbox")
async def gmail_inbox():
    token_doc = google_tokens.find_one({"provider": "gmail"})

    if not token_doc:
        return {"gmail_connected": False, "error": "No refresh token"}

    creds = Credentials(
        token=None,
        refresh_token=token_doc["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        scopes=["https://www.googleapis.com/auth/gmail.readonly"],
    )

    try:
        service = build("gmail", "v1", credentials=creds)

        result = service.users().messages().list(
            userId="me",
            maxResults=10
        ).execute()

        messages = []

        for item in result.get("messages", []):
            msg = service.users().messages().get(
                userId="me",
                id=item["id"],
                format="full"
            ).execute()

            headers = {
                h["name"]: h["value"]
                for h in msg.get("payload", {}).get("headers", [])
            }

            sender = headers.get("From", "")
            subject = headers.get("Subject", "")
            
            # Get plain-text body
            body = ""

            payload = msg.get("payload", {})

            if payload.get("body", {}).get("data"):
                import base64
                body = base64.urlsafe_b64decode(
                    payload["body"]["data"]
                ).decode("utf-8", errors="ignore")

            elif payload.get("parts"):
                for part in payload["parts"]:
                    if part.get("mimeType") == "text/plain":
                        data = part.get("body", {}).get("data")
                        if data:
                            import base64
                            body = base64.urlsafe_b64decode(
                                data
                            ).decode("utf-8", errors="ignore")
                        break

            lead_id = f"email_{sender.lower()}"
            conversation_id = f"email_{sender.lower()}"

            # Create lead
            if not get_lead(lead_id):
                lead = Lead(
                    lead_id=lead_id,
                    channel="email",
                    sender_id=sender,
                )
                create_lead(lead.model_dump())

            # Create conversation
            if not get_conversation(conversation_id):
                conversation = Conversation(
                    conversation_id=conversation_id,
                    lead_id=lead_id,
                    channel="email",
                    sender_id=sender,
                )
                create_conversation(conversation.model_dump())

            # Avoid saving the same email twice
            existing_messages = list(
                messages_collection.find({
                    "conversation_id": conversation_id,
                    "provider_message_id": item["id"]
                })
            )

            if not existing_messages:
                message = Message(
                    conversation_id=conversation_id,
                    lead_id=lead_id,
                    channel="email",
                    sender_id=sender,
                    direction="inbound",
                    content=f"Subject: {subject}\n\n{body}",
                    provider_message_id=item["id"],
                )

                create_message(message.model_dump())

                print("EMAIL MESSAGE SAVED TO MONGODB")
                print("Lead:", lead_id)
                print("Conversation:", conversation_id)
                print("Subject:", subject)

            messages.append({
                "id": item["id"],
                "from": sender,
                "subject": subject,
                "saved": True,
            })

        return {
            "gmail_connected": True,
            "messages": messages,
        }

    except Exception as e:
        return {
            "gmail_connected": False,
            "error": str(e),
        }

@app.get("/privacy-policy", response_class=HTMLResponse) #this endpoint serves the privacy policy page for the application
async def privacy_policy():
    return """
    <html>
    <head><title>Privacy Policy</title></head>
    <body>
        <h1>Privacy Policy</h1>
        <p>This application is a test AI sales assistant created for development and evaluation.</p>
        <p>We use information received through connected messaging services only to demonstrate
        message handling, lead qualification, scheduling, and related application functionality.</p>
        <p>Test data is used only for this project and is not sold to third parties.</p>
        <p>For questions about this application, contact the developer through the project repository.</p>
    </body>
    </html>
    """