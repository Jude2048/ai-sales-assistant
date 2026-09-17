import os
from urllib.parse import urlencode
from fastapi import FastAPI
from contextlib import asynccontextmanager
import asyncio
from api.assignment1.conversation_engine import generate_reply
from api.webhooks.instagram import router as instagram_router
from fastapi.responses import HTMLResponse, RedirectResponse
from api.webhooks.whatsapp import router as whatsapp_router
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from pymongo import MongoClient
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import shared.mongo
from shared.schemas import Lead, Conversation, Message
from api.assignment1.whatsapp_adapter import WhatsAppAdapter
from pydantic import BaseModel
from api.assignment1.instagram_adapter import InstagramAdapter
from api.assignment1.gmail_adapter import GmailAdapter
from shared.gemini import generate_response
from api.assignment1.gmail_adapter import GmailAdapter
from api.assignment1.conversation_engine import generate_reply
from email.utils import parseaddr
from api.assignment1.conversation_engine import qualify_lead, generate_reply, qualify_lead, get_selected_booking_slot, is_booking_confirmation
from datetime import datetime

from api.assignment1.calendar_adapter import GoogleCalendarAdapter
from datetime import datetime

from api.assignment1.booking_service import book_meeting
import json
    
    

mongo_client = MongoClient(os.getenv("MONGODB_URI"))
db = mongo_client["ai_sales_assistant"]
google_tokens = db["google_tokens"] 

@asynccontextmanager #This is a context manager that runs the Gmail polling loop in the background while the FastAPI app is running. It starts the loop when the app starts and cancels it when the app shuts down.
async def lifespan(app: FastAPI):
    task = asyncio.create_task(gmail_poll_loop()) #This starts the Gmail polling loop in the background when the FastAPI app starts. It runs the loop in a separate task so that it doesn't block the main thread. The loop will continue to run until the app is shut down, at which point the task will be cancelled and the loop will stop.

    yield

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

# Create FastAPI app after lifespan is defined
app = FastAPI(title="AI Sales Assistant", lifespan=lifespan)

app.include_router(instagram_router, prefix="/webhooks")
app.include_router(whatsapp_router, prefix="/webhooks")

@app.get("/")
async def root():
    return {"status": "ok"}


class WhatsAppTestRequest(BaseModel):
    to: str
    message: str


@app.post("/debug/whatsapp/send")
async def test_whatsapp_send(request: WhatsAppTestRequest):
    adapter = WhatsAppAdapter()

    result = adapter.send(
        recipient=request.to,
        message=request.message,
    )

    return result

class InstagramTestRequest(BaseModel):
    to: str
    message: str


@app.post("/debug/instagram/send")
async def test_instagram_send(request: InstagramTestRequest):
    adapter = InstagramAdapter()

    return adapter.send(
        recipient=request.to,
        message=request.message,
    )

class GmailTestRequest(BaseModel):
    to: str
    subject: str
    message: str


@app.post("/debug/gmail/send")
async def test_gmail_send(request: GmailTestRequest):
    adapter = GmailAdapter(google_tokens)

    return adapter.send(
        recipient=request.to,
        subject=request.subject,
        message=request.message,
    )


@app.get("/debug/gemini")
async def debug_gemini():
    response = generate_response(
        "Reply with exactly: Gemini connection works."
    )
    return {"response": response}

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
        "scope": "https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/calendar",
        "access_type": "offline",
        "prompt": "consent",
    }

    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)

    return RedirectResponse(url)

@app.get("/debug/gmail/inbox") #this endpoint is for debugging and testing Gmail inbox polling
async def gmail_inbox(): #Returns the latest 10 emails from the Gmail inbox and saves them to MongoDB if they are new
    return await poll_gmail_inbox() 

async def poll_gmail_inbox():
    token_doc = google_tokens.find_one({"provider": "gmail"})

    if not token_doc:
        return {
            "gmail_connected": False,
            "error": "No refresh token"
        }

    creds = Credentials(
        token=None,
        refresh_token=token_doc["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        scopes=[
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/calendar",
        ],
    )

    try:
        service = build(
            "gmail",
            "v1",
            credentials=creds
        )

        result = service.users().messages().list(
            userId="me",
            labelIds=["INBOX"],
            maxResults=10
        ).execute()

        messages = []

        for item in result.get("messages", []):

            gmail_message_id = item["id"]

            existing_message = shared.mongo.messages_collection.find_one({
                "channel": "email",
                "provider_message_id": gmail_message_id,
            })

            if existing_message:
                continue

            msg = service.users().messages().get(
                userId="me",
                id=gmail_message_id,
                format="full"
            ).execute()

            headers = {
                h["name"]: h["value"]
                for h in msg.get("payload", {}).get("headers", [])
            }

            sender = headers.get("From", "")
            sender_name, sender_email = parseaddr(sender)

            if sender_email.lower() == "ai.sales.assistant.test@gmail.com":
                continue

            subject = headers.get("Subject", "")
            original_message_id = headers.get("Message-ID")

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

            lead_id = f"email_{sender_email.lower()}"
            conversation_id = f"email_{item['threadId']}"

            # Get or create lead
            lead = shared.mongo.get_lead(lead_id)

            if not lead:
                lead_obj = Lead(
                    lead_id=lead_id,
                    channel="email",
                    sender_id=sender_email,
                    sender_name=sender_name or None,
                )

                shared.mongo.create_lead(lead_obj.model_dump())
                lead = lead_obj.model_dump()

            # Get or create conversation
            conversation = shared.mongo.get_conversation(conversation_id)

            if not conversation:
                conversation_obj = Conversation(
                    conversation_id=conversation_id,
                    lead_id=lead_id,
                    channel="email",
                    sender_id=sender_email,
                )

                shared.mongo.create_conversation(
                    conversation_obj.model_dump()
                )

            # Save inbound
            message = Message(
                conversation_id=conversation_id,
                lead_id=lead_id,
                channel="email",
                sender_id=sender_email,
                direction="inbound",
                content=f"Subject: {subject}\n\n{body}",
                provider_message_id=gmail_message_id,
            )

            shared.mongo.create_message(message.model_dump())

            print("EMAIL MESSAGE SAVED TO MONGODB")

            # Human takeover
            if not lead.get("automation_enabled", True):
                print("AUTOMATION DISABLED - HUMAN TAKEOVER")
                continue

            # Refresh lead because previous messages may have changed it
            lead = shared.mongo.get_lead(lead_id)

            # =====================================================
            # BOOKING FLOW
            # =====================================================

            selected_slot = get_selected_booking_slot(
                lead,
                body
            )

            if selected_slot:

                update_lead(
                    lead_id,
                    {
                        "pending_booking": {
                            "slot": selected_slot,
                            "status": "awaiting_confirmation",
                        }
                    },
                )

                slot_time = datetime.fromisoformat(selected_slot)

                reply = (
                    f"You selected {slot_time.strftime('%A, %d %B at %H:%M')}. "
                    "Would you like me to confirm this booking?"
                )

            elif lead.get("pending_booking", {}).get("status") == "awaiting_confirmation":

                if is_booking_confirmation(body):

                    pending = lead["pending_booking"]
                    selected_slot = pending["slot"]

                    start_time = datetime.fromisoformat(
                        selected_slot
                    )

                    booking_result = book_meeting(
                        lead_id=lead_id,
                        conversation_id=conversation_id,
                        attendee_email=sender_email,
                        start_time=start_time,
                        duration_minutes=30,
                        google_tokens_collection=google_tokens,
                    )

                    print("GMAIL BOOKING RESULT:", booking_result)

                    if booking_result["status"] == "confirmed":

                        update_lead(
                            lead_id,
                            {
                                "pending_booking": {
                                    "slot": selected_slot,
                                    "status": "confirmed",
                                },
                                "meeting_status": "confirmed",
                            },
                        )

                        reply = (
                            f"Your consultation is confirmed for "
                            f"{start_time.strftime('%A, %d %B at %H:%M')}."
                        )

                    elif booking_result["status"] == "already_booked":

                        update_lead(
                            lead_id,
                            {
                                "pending_booking": {
                                    "slot": selected_slot,
                                    "status": "confirmed",
                                },
                                "meeting_status": "confirmed",
                            },
                        )

                        reply = "This consultation has already been booked."

                    else:

                        update_lead(
                            lead_id,
                            {
                                "pending_booking": {
                                    "status": "slot_unavailable",
                                }
                            },
                        )

                        reply = (
                            "Sorry, that slot is no longer available. "
                            "Please choose another available time."
                        )

                else:

                    reply = (
                        "Please reply with 'yes' to confirm the selected "
                        "time, or choose another available slot."
                    )

            else:

                # =================================================
                # QUALIFICATION
                # =================================================

                qualification = qualify_lead(
                    conversation_id=conversation_id,
                    new_message=body,
                )

                print("GMAIL QUALIFICATION:", qualification)

                status = qualification["qualification"]["status"]

                if status == "needs_information":

                    reply = qualification["qualification"]["follow_up"]

                elif status == "qualified":

                    reply = qualification["qualification"]["slot_message"]

                elif status == "not_qualified":

                    reply = (
                        "Thank you for sharing those details. "
                        "Unfortunately, your requirements do not meet "
                        "our current qualification criteria."
                    )

                else:

                    reply = (
                        "Thank you for your message. "
                        "We'll review your requirements and get back to you."
                    )

            # =====================================================
            # SEND EMAIL
            # =====================================================

            adapter = GmailAdapter(google_tokens)

            adapter.send(
                recipient=sender_email,
                subject=f"Re: {subject}",
                message=reply,
                thread_id=item["threadId"],
                in_reply_to=original_message_id,
            )

            shared.mongo.create_message(
                Message(
                    conversation_id=conversation_id,
                    lead_id=lead_id,
                    channel="email",
                    sender_id="sales_assistant",
                    direction="outbound",
                    content=reply,
                ).model_dump()
            )

            print("GMAIL AI REPLY SAVED TO MONGODB")

            messages.append({
                "id": gmail_message_id,
                "from": sender,
                "subject": subject,
                "saved": True,
            })

        return {
            "gmail_connected": True,
            "messages": messages,
        }

    except Exception as e:

        print("GMAIL POLLING ERROR:", str(e))

        return {
            "gmail_connected": False,
            "error": str(e),
        }

async def gmail_poll_loop():
    while True:
        try:
            await poll_gmail_inbox()
        except Exception as e:
            print("GMAIL POLLING ERROR:", e)

        await asyncio.sleep(60)

class QualificationTestRequest(BaseModel):
    conversation_id: str
    message: str


@app.post("/debug/qualify")
async def test_qualification(request: QualificationTestRequest):
    return qualify_lead(
        conversation_id=request.conversation_id,
        new_message=request.message,
    )

@app.get("/debug/calendar/availability")
async def debug_calendar_availability():
    from shared.mongo import google_tokens_collection

    calendar = GoogleCalendarAdapter(
        shared.mongo.google_tokens_collection
    )

    start = datetime.fromisoformat(
        "2026-09-18T09:00:00+01:00"
    )

    end = datetime.fromisoformat(
        "2026-09-18T17:00:00+01:00"
    )

    busy = calendar.get_availability(
        start,
        end,
    )

    return {
        "status": "ok",
        "busy": busy,
    }

@app.post("/debug/calendar/book")
async def debug_calendar_book():
    result = book_meeting(
        lead_id="test_lead",
        conversation_id="test_conversation",
        attendee_email="judesilveira1@gmail.com",
        start_time=datetime.fromisoformat(
            "2026-09-18T10:00:00+01:00"
        ),
        duration_minutes=30,
        google_tokens_collection=shared.mongo.google_tokens_collection,
    )

    return result

@app.get("/api/leads")
async def api_get_leads():
    leads = list(
        shared.mongo.leads_collection.find(
            {},
            {"_id": 0}
        ).sort("updated_at", -1)
    )

    return {
        "leads": leads
    }


@app.get("/api/leads/{lead_id}")
async def api_get_lead(lead_id: str):
    lead = shared.mongo.get_lead(lead_id)

    if not lead:
        return {
            "error": "Lead not found"
        }

    lead.pop("_id", None)

    return lead


@app.get("/api/leads/{lead_id}/conversation")
async def api_get_conversation(lead_id: str):
    conversation = shared.mongo.conversations_collection.find_one(
        {"lead_id": lead_id}
    )

    if not conversation:
        return {
            "conversation": None,
            "messages": []
        }

    conversation.pop("_id", None)

    messages = shared.mongo.get_messages(
        conversation["conversation_id"]
    )

    for message in messages:
        message.pop("_id", None)

    return {
        "conversation": conversation,
        "messages": messages
    }


@app.get("/api/leads/{lead_id}/actions")
async def api_get_actions(lead_id: str):

    # Action log collection
    actions_collection = shared.mongo.db["action_log"]

    actions = list(
        actions_collection.find(
            {"lead_id": lead_id},
            {"_id": 0}
        ).sort("created_at", -1)
    )

    return {
        "actions": actions
    }


class AutomationRequest(BaseModel):
    enabled: bool


@app.post("/api/leads/{lead_id}/automation")
async def api_update_automation(
    lead_id: str,
    request: AutomationRequest,
):

    lead = shared.mongo.get_lead(lead_id)

    if not lead:
        return {
            "error": "Lead not found"
        }

    shared.mongo.update_lead(
        lead_id,
        {
            "automation_enabled": request.enabled,
            "updated_at": datetime.utcnow(),
        },
    )

    return {
        "status": "updated",
        "lead_id": lead_id,
        "automation_enabled": request.enabled,
    }


@app.get("/api/bookings/{lead_id}")
async def api_get_booking(lead_id: str):

    booking = shared.mongo.get_booking_by_lead(
        lead_id
    )

    if not booking:
        return {
            "booking": None
        }

    booking.pop("_id", None)

    return {
        "booking": booking
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