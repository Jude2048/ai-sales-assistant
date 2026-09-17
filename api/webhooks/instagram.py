import os
from pydoc import text

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse
from api.assignment1.conversation_engine import generate_reply, qualify_lead
from api.assignment1.instagram_adapter import InstagramAdapter


from shared.mongo import (
    create_lead,
    create_conversation,
    create_message,
    get_lead,
    get_conversation,
)
from shared.schemas import Lead, Conversation, Message

router = APIRouter() #This router will handle Instagram webhook endpoints

VERIFY_TOKEN = os.getenv("INSTAGRAM_VERIFY_TOKEN")


@router.get("/instagram", response_class=PlainTextResponse) #endpoint for Instagram webhook verification
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

        # Ignore Instagram echo messages
        if message_data.get("is_echo"):
            print("INSTAGRAM ECHO IGNORED")
            return {"status": "ignored_echo"}

        text = message_data.get("text", "")
        provider_message_id = message_data.get("mid")

        if not text:
            return {"status": "received", "saved": False}

        channel = "instagram"
        lead_id = f"instagram_{sender_id}"
        conversation_id = f"instagram_{sender_id}"

        # Create lead if it doesn't exist
        lead = get_lead(lead_id)

        if not lead:
            lead_obj = Lead(
                lead_id=lead_id,
                channel=channel,
                sender_id=sender_id,
            )

            create_lead(lead_obj.model_dump())
            lead = lead_obj.model_dump()

        # Create conversation if it doesn't exist
        conversation = get_conversation(conversation_id)

        if not conversation:
            conversation_obj = Conversation(
                conversation_id=conversation_id,
                lead_id=lead_id,
                channel=channel,
                sender_id=sender_id,
            )

            create_conversation(conversation_obj.model_dump())

        # Save inbound message
        message_obj = Message(
            conversation_id=conversation_id,
            lead_id=lead_id,
            channel=channel,
            sender_id=sender_id,
            direction="inbound",
            content=text,
            provider_message_id=provider_message_id,
        )

        create_message(message_obj.model_dump())

        print("INSTAGRAM MESSAGE SAVED TO MONGODB")
        print("Lead:", lead_id)
        print("Conversation:", conversation_id)
        print("Message:", text)

        # Human takeover check
        if not lead.get("automation_enabled", True):
            print("INSTAGRAM AUTOMATION DISABLED")
            return {
                "status": "received",
                "saved": True,
                "automation": "disabled",
            }

        # Qualification FIRST
        qualification = qualify_lead(
            conversation_id=conversation_id,
            new_message=text,
        )

        print("INSTAGRAM QUALIFICATION:", qualification)

        # Generate appropriate reply
        if qualification["qualification"]["status"] == "needs_information":
            reply = qualification["qualification"]["follow_up"]

        elif qualification["qualification"]["status"] == "qualified":
             reply = qualification["qualification"]["slot_message"]

        else:
             reply = generate_reply(
                 conversation_id=conversation_id,
                new_message=text,
            )

        # Send reply
        adapter = InstagramAdapter()

        adapter.send(
            recipient=sender_id,
            message=reply,
        )

        # Save outbound message
        create_message(
            Message(
                conversation_id=conversation_id,
                lead_id=lead_id,
                channel="instagram",
                sender_id=17841423916787536,
                direction="outbound",
                content=reply,
            ).model_dump()
        )

        print("INSTAGRAM AI REPLY SAVED TO MONGODB")

        return {
            "status": "received",
            "saved": True,
            "lead_id": lead_id,
            "conversation_id": conversation_id,
        }

    except Exception as e:
        print("Instagram persistence error:", str(e))

        return {
            "status": "received",
            "saved": False,
            "error": str(e),
        }