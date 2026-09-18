import os
from urllib.parse import urlencode
from fastapi import FastAPI
from contextlib import asynccontextmanager
import asyncio
from api.assignment1.conversation_engine import generate_reply, get_booking_slots
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
from zoneinfo import ZoneInfo

from api.assignment1.calendar_adapter import GoogleCalendarAdapter
from datetime import datetime
from api.assignment2.routes import router as assignment2_router
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
app.include_router(assignment2_router)
app.include_router(instagram_router, prefix="/webhooks")
app.include_router(whatsapp_router, prefix="/webhooks")

@app.get("/")
async def root():
    return {"status": "ok"}


class WhatsAppTestRequest(BaseModel):
    to: str
    message: str




class InstagramTestRequest(BaseModel):
    to: str
    message: str




class GmailTestRequest(BaseModel):
    to: str
    subject: str
    message: str


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

            # Prevent processing the same Gmail message more than once.
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

            sender_email = sender_email.strip().lower()

            # Ignore emails sent by the assistant itself.
            if sender_email == "ai.sales.assistant.test@gmail.com":
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

            body = body.strip()

            lead_id = f"email_{sender_email}"
            conversation_id = f"email_{item['threadId']}"

            # ---------------------------------------------------------
            # GET OR CREATE LEAD
            # ---------------------------------------------------------

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

            # ---------------------------------------------------------
            # GET OR CREATE CONVERSATION
            # ---------------------------------------------------------

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

            # ---------------------------------------------------------
            # SAVE INBOUND MESSAGE
            # ---------------------------------------------------------

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

            # Refresh lead after message persistence.
            lead = shared.mongo.get_lead(lead_id)

            # ---------------------------------------------------------
            # HUMAN TAKEOVER
            # ---------------------------------------------------------

            if not lead.get("automation_enabled", True):
                messages.append({
                    "id": gmail_message_id,
                    "from": sender,
                    "subject": subject,
                    "saved": True,
                    "automation": "disabled",
                })
                continue

            # ---------------------------------------------------------
            # ALREADY BOOKED
            #
            # Once a meeting is confirmed, do NOT enter the scheduling
            # flow again on later emails.
            # ---------------------------------------------------------

            existing_booking = shared.mongo.get_booking_by_lead(lead_id)

            if (
                existing_booking
                and existing_booking.get("status") == "confirmed"
            ) or lead.get("meeting_status") == "confirmed":

                start_time = None

                if existing_booking:
                    existing_start = existing_booking.get("start_time")

                    if existing_start:
                        if isinstance(existing_start, datetime):
                            start_time = existing_start
                        else:
                            try:
                                start_time = datetime.fromisoformat(
                                    str(existing_start)
                                )
                            except Exception:
                                start_time = None

                if start_time:
                    reply = (
                        "Your consultation is already confirmed for "
                        f"{start_time.strftime('%A, %d %B at %H:%M')}. "
                        "If you have another question, I'm happy to help."
                    )
                else:
                    reply = (
                        "Your consultation is already confirmed. "
                        "If you have another question, I'm happy to help."
                    )

            else:

                # -----------------------------------------------------
                # BOOKING STATE
                # -----------------------------------------------------

                pending_booking = lead.get("pending_booking") or {}
                pending_status = pending_booking.get("status")

                # -----------------------------------------------------
                # STEP 1: CUSTOMER SELECTED 1 / 2 / 3
                # -----------------------------------------------------

                if (
                    pending_status == "awaiting_selection"
                    and body.strip() in {"1", "2", "3"}
                ):

                    selected_slot = get_selected_booking_slot(
                        lead,
                        body
                    )

                    if selected_slot:

                        slot_time = datetime.fromisoformat(selected_slot)

                        # Never allow a previously offered slot that has now passed.
                        london_now = datetime.now(ZoneInfo("Europe/London"))

                        if slot_time <= london_now:

                            # Generate fresh slots.
                            fresh_slots = get_booking_slots()

                            if fresh_slots:

                                fresh_slot_strings = [
                                    slot.isoformat()
                                    for slot in fresh_slots
                                ]

                                shared.mongo.update_lead(
                                    lead_id,
                                    {
                                        "pending_booking": {
                                            "slots": fresh_slot_strings,
                                            "status": "awaiting_selection",
                                        },
                                        "updated_at": datetime.utcnow(),
                                    }
                                )

                                reply = (
                                    "The previously offered times have expired. "
                                    "Here are the current available times:\n\n"
                                    + "\n".join(
                                        f"{i + 1}. "
                                        f"{slot.strftime('%A, %d %B at %H:%M')}"
                                        for i, slot in enumerate(fresh_slots)
                                    )
                                    + "\n\nPlease reply with the number of your preferred slot."
                                )

                            else:

                                shared.mongo.update_lead(
                                    lead_id,
                                    {
                                        "pending_booking": None,
                                        "updated_at": datetime.utcnow(),
                                    }
                                )

                                reply = (
                                    "The previously offered times have expired and "
                                    "there are currently no available consultation slots."
                                )

                        else:

                            shared.mongo.update_lead(
                                lead_id,
                                {
                                    "pending_booking": {
                                        "slot": selected_slot,
                                        "status": "awaiting_confirmation",
                                    },
                                    "updated_at": datetime.utcnow(),
                                }
                            )

                            reply = (
                                f"You selected "
                                f"{slot_time.strftime('%A, %d %B at %H:%M')}. "
                                "Would you like me to confirm this booking?"
                            )

                    else:

                        # This is not a slot selection.
                        # Clear stale selection state and process the message
                        # normally through qualification/conversation logic.

                        shared.mongo.update_lead(
                            lead_id,
                            {
                                "pending_booking": None,
                                "updated_at": datetime.utcnow(),
                            }
                        )

                        qualification = qualify_lead(
                            conversation_id=conversation_id,
                            new_message=body,
                        )

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

                # -----------------------------------------------------
                # STEP 2: CUSTOMER CONFIRMS SELECTED SLOT
                # -----------------------------------------------------

                elif pending_status == "awaiting_confirmation":

                    if is_booking_confirmation(body):

                        selected_slot = pending_booking.get("slot")

                        if not selected_slot:
                            shared.mongo.update_lead(
                                lead_id,
                                {
                                    "pending_booking": None,
                                    "updated_at": datetime.utcnow(),
                                }
                            )

                            reply = (
                                "The selected meeting time is no longer "
                                "available. Please choose from the available "
                                "times again."
                            )

                        else:

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

                            if booking_result["status"] == "confirmed":

                                shared.mongo.update_lead(
                                    lead_id,
                                    {
                                        "status": "booked",
                                        "pending_booking": {
                                            "slot": selected_slot,
                                            "status": "confirmed",
                                        },
                                        "meeting_status": "confirmed",
                                        "updated_at": datetime.utcnow(),
                                    }
                                )

                                reply = (
                                    "Your consultation is confirmed for "
                                    f"{start_time.strftime('%A, %d %B at %H:%M')}. "
                                    "You will receive the calendar invitation shortly."
                                )

                            elif booking_result["status"] == "already_booked":

                                shared.mongo.update_lead(
                                    lead_id,
                                    {
                                        "status": "booked",
                                        "pending_booking": {
                                            "slot": selected_slot,
                                            "status": "confirmed",
                                        },
                                        "meeting_status": "confirmed",
                                        "updated_at": datetime.utcnow(),
                                    }
                                )

                                reply = (
                                    "Your consultation is already confirmed for "
                                    f"{start_time.strftime('%A, %d %B at %H:%M')}."
                                )

                            elif booking_result["status"] == "slot_unavailable":

                                shared.mongo.update_lead(
                                    lead_id,
                                    {
                                        "pending_booking": {
                                            "status": "slot_unavailable"
                                        },
                                        "updated_at": datetime.utcnow(),
                                    }
                                )

                                reply = (
                                    "Sorry, that slot is no longer available. "
                                    "Please choose another available time."
                                )

                            else:

                                # Do not blindly retry uncertain bookings.
                                reply = (
                                    "I couldn't confirm the meeting because "
                                    "the calendar response was uncertain. "
                                    "Please try again or contact the team."
                                )

                    else:

                        reply = (
                            "Please reply with 'yes' to confirm the selected "
                            "time."
                        )

                # -----------------------------------------------------
                # STEP 3: SLOT WAS UNAVAILABLE
                # -----------------------------------------------------

                elif pending_status == "slot_unavailable":

                    # Clear the stale booking state so qualification can
                    # generate a fresh set of available slots.
                    shared.mongo.update_lead(
                        lead_id,
                        {
                            "pending_booking": None,
                            "updated_at": datetime.utcnow(),
                        }
                    )

                    qualification = qualify_lead(
                        conversation_id=conversation_id,
                        new_message=body,
                    )

                    status = qualification["qualification"]["status"]

                    if status == "qualified":
                        reply = qualification["qualification"]["slot_message"]

                    elif status == "needs_information":
                        reply = qualification["qualification"]["follow_up"]

                    else:
                        reply = (
                            "Thank you for sharing those details. "
                            "Unfortunately, your requirements do not meet "
                            "our current qualification criteria."
                        )

                # -----------------------------------------------------
                # STEP 4: NORMAL QUALIFICATION
                # -----------------------------------------------------

                else:

                    qualification = qualify_lead(
                        conversation_id=conversation_id,
                        new_message=body,
                    )

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

            # ---------------------------------------------------------
            # SEND EMAIL
            # ---------------------------------------------------------

            adapter = GmailAdapter(google_tokens)

            adapter.send(
                recipient=sender_email,
                subject=f"Re: {subject}",
                message=reply,
                thread_id=item["threadId"],
                in_reply_to=original_message_id,
            )

            # ---------------------------------------------------------
            # SAVE OUTBOUND MESSAGE
            # ---------------------------------------------------------

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

        return {
            "gmail_connected": False,
            "error": str(e),
        }


async def gmail_poll_loop():
    while True:

        try:
            await poll_gmail_inbox()

        except Exception as e:
            # Keep the polling service alive if one polling cycle fails.
            print("Gmail polling cycle failed:", str(e))

        await asyncio.sleep(60)

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

@app.get("/debug/calendar/availability")
async def debug_calendar_availability():
    try:
        calendar = GoogleCalendarAdapter(
            shared.mongo.google_tokens_collection
        )

        now = datetime.now().astimezone()

        start = now.replace(
            hour=9,
            minute=0,
            second=0,
            microsecond=0,
        )

        end = now.replace(
            hour=17,
            minute=0,
            second=0,
            microsecond=0,
        )

        busy = calendar.get_availability(start, end)

        return {
            "status": "ok",
            "calendar_connected": True,
            "date": start.date().isoformat(),
            "timezone": str(start.tzinfo),
            "busy": busy,
        }

    except Exception as e:
        return {
            "status": "error",
            "calendar_connected": False,
            "error": str(e),
        }

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