import os
from pydoc import text

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse
from api.assignment1.conversation_engine import generate_reply, qualify_lead, get_selected_booking_slot, is_booking_confirmation
from api.assignment1.instagram_adapter import InstagramAdapter
from datetime import datetime
import shared.mongo
from api.assignment1.booking_service import book_meeting

from shared.schemas import Lead, Conversation, Message

router = APIRouter() #This router will handle Instagram webhook endpoints

VERIFY_TOKEN = os.getenv("INSTAGRAM_VERIFY_TOKEN")


@router.get("/instagram", response_class=PlainTextResponse)
async def verify_instagram_webhook(
    hub_mode: str | None = None,
    hub_verify_token: str | None = None,
    hub_challenge: str | None = None,
):
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return hub_challenge or ""

    return "Verification failed"


@router.post("/instagram")
async def receive_instagram_webhook(request: Request):
    payload = await request.json()

    print("Instagram webhook received:")
    print(payload)

    try:
        entry = payload["entry"][0]
        messaging = entry["messaging"][0]

        sender_id = str(messaging["sender"]["id"])
        message_data = messaging.get("message", {})

        if message_data.get("is_echo"):
            print("INSTAGRAM ECHO IGNORED")
            return {"status": "ignored_echo"}

        text = message_data.get("text", "")
        provider_message_id = message_data.get("mid")

        if not text:
            return {
                "status": "received",
                "saved": False,
            }

        channel = "instagram"
        lead_id = f"instagram_{sender_id}"
        conversation_id = f"instagram_{sender_id}"

        # ------------------------------------------------
        # GET OR CREATE LEAD
        # ------------------------------------------------

        lead = shared.mongo.get_lead(lead_id)

        if not lead:
            lead_obj = Lead(
                lead_id=lead_id,
                channel=channel,
                sender_id=sender_id,
            )

            shared.mongo.create_lead(lead_obj.model_dump())
            lead = lead_obj.model_dump()

        # ------------------------------------------------
        # GET OR CREATE CONVERSATION
        # ------------------------------------------------

        conversation = shared.mongo.get_conversation(conversation_id)

        if not conversation:
            conversation_obj = Conversation(
                conversation_id=conversation_id,
                lead_id=lead_id,
                channel=channel,
                sender_id=sender_id,
            )

            shared.mongo.create_conversation(
                conversation_obj.model_dump()
            )

        # ------------------------------------------------
        # SAVE INBOUND MESSAGE
        # ------------------------------------------------

        shared.mongo.create_message(
            Message(
                conversation_id=conversation_id,
                lead_id=lead_id,
                channel=channel,
                sender_id=sender_id,
                direction="inbound",
                content=text,
                provider_message_id=provider_message_id,
            ).model_dump()
        )

        print("INSTAGRAM MESSAGE SAVED TO MONGODB")

        # ------------------------------------------------
        # HUMAN TAKEOVER
        # ------------------------------------------------

        if not lead.get("automation_enabled", True):
            return {
                "status": "received",
                "saved": True,
                "automation": "disabled",
            }

        # ------------------------------------------------
        # BOOKING FLOW
        # ------------------------------------------------

        # First: if this lead already has a confirmed booking,
        # never enter the scheduling flow again.
        existing_booking = shared.mongo.get_booking_by_lead(lead_id)

        if (
            existing_booking
            and existing_booking.get("status") == "confirmed"
        ) or lead.get("meeting_status") == "confirmed":

            if existing_booking and existing_booking.get("start_time"):
                existing_start = existing_booking.get("start_time")

                if isinstance(existing_start, datetime):
                    confirmed_time = existing_start
                else:
                    try:
                        confirmed_time = datetime.fromisoformat(
                            str(existing_start)
                        )
                    except Exception:
                        confirmed_time = None
            else:
                confirmed_time = None

            if confirmed_time:
                reply = (
                    "Your consultation is already confirmed for "
                    f"{confirmed_time.strftime('%A, %d %B at %H:%M')}. "
                    "If you have another question, I'm happy to help."
                )
            else:
                reply = (
                    "Your consultation is already confirmed. "
                    "If you have another question, I'm happy to help."
                )

        else:
            # ------------------------------------------------
            # CHECK FOR SELECTED BOOKING SLOT
            # ------------------------------------------------

            selected_slot = get_selected_booking_slot(
                lead,
                text,
            )

            if selected_slot:
                shared.mongo.update_lead(
                    lead_id,
                    {
                        "pending_booking": {
                            "slot": selected_slot,
                            "status": "awaiting_confirmation",
                        },
                        "updated_at": datetime.utcnow(),
                    },
                )

                reply = (
                    "You selected "
                    f"{datetime.fromisoformat(selected_slot).strftime('%A, %d %B at %H:%M')}. "
                    "Would you like me to confirm this booking?"
                )

            # ------------------------------------------------
            # AWAITING BOOKING CONFIRMATION
            # ------------------------------------------------

            elif (
                lead.get("pending_booking", {}).get("status")
                == "awaiting_confirmation"
            ):

                if is_booking_confirmation(text):
                    pending = lead["pending_booking"]
                    selected_slot = pending["slot"]

                    start_time = datetime.fromisoformat(selected_slot)

                    result = book_meeting(
                        lead_id=lead_id,
                        conversation_id=conversation_id,
                        attendee_email=None,
                        start_time=start_time,
                        duration_minutes=30,
                        google_tokens_collection=(
                            shared.mongo.google_tokens_collection
                        ),
                    )

                    if result["status"] == "confirmed":
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
                            },
                        )

                        reply = (
                            "Your consultation is confirmed for "
                            f"{start_time.strftime('%A, %d %B at %H:%M')}."
                        )

                    elif result["status"] == "already_booked":
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
                            },
                        )

                        reply = (
                            "This consultation has already been booked."
                        )

                    elif result["status"] == "slot_unavailable":
                        shared.mongo.update_lead(
                            lead_id,
                            {
                                "pending_booking": {
                                    "status": "slot_unavailable",
                                },
                                "updated_at": datetime.utcnow(),
                            },
                        )

                        reply = (
                            "Sorry, that slot is no longer available. "
                            "Please choose another available time."
                        )

                    else:
                        # Do not blindly retry an uncertain
                        # calendar operation.
                        reply = (
                            "I couldn't confirm the booking because the "
                            "calendar response was uncertain. Please try again."
                        )

                else:
                    reply = (
                        "Please reply with 'yes' to confirm the selected "
                        "time, or choose another slot."
                    )

            # ------------------------------------------------
            # QUALIFICATION
            # ------------------------------------------------

            else:
                qualification = qualify_lead(
                    conversation_id=conversation_id,
                    new_message=text,
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

        # ------------------------------------------------
        # SEND REPLY
        # ------------------------------------------------

        adapter = InstagramAdapter()

        adapter.send(
            recipient=sender_id,
            message=reply,
        )

        # ------------------------------------------------
        # SAVE OUTBOUND MESSAGE
        # ------------------------------------------------

        shared.mongo.create_message(
            Message(
                conversation_id=conversation_id,
                lead_id=lead_id,
                channel=channel,
                sender_id=str(17841423916787536),
                direction="outbound",
                content=reply,
            ).model_dump()
        )

        return {
            "status": "received",
            "saved": True,
            "lead_id": lead_id,
            "conversation_id": conversation_id,
        }

    except Exception as e:
        print(f"INSTAGRAM WEBHOOK ERROR: {e}")

        return {
            "status": "error",
            "message": str(e),
        }