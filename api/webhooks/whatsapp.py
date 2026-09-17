from email.mime import text

from fastapi import APIRouter, Request
from shared.mongo import (
    create_lead,
    create_conversation,
    create_message,
    get_lead,
    get_conversation,
)
from api.assignment1.conversation_engine import qualify_lead
from shared.schemas import Lead, Conversation, Message
from api.assignment1.conversation_engine import (
    generate_reply,
    qualify_lead,
)

router = APIRouter()


@router.post("/whatsapp")
async def receive_whatsapp_webhook(request: Request):
    form = await request.form()
    payload = dict(form)

    print("WhatsApp webhook received:")
    print(payload)

    try:
        sender_id = payload.get("From")
        text = payload.get("Body", "")
        provider_message_id = payload.get("MessageSid")

        if not sender_id or not text:
            return {"status": "received", "saved": False}

        channel = "whatsapp"

        # Keep WhatsApp conversations separate from other channels
        lead_id = f"whatsapp_{sender_id}"
        conversation_id = f"whatsapp_{sender_id}"

        # --------------------------------------------------
        # 1. Get or create lead
        # --------------------------------------------------

        lead = get_lead(lead_id)

        if not lead:
            lead_obj = Lead(
                lead_id=lead_id,
                channel=channel,
                sender_id=sender_id,
            )

            create_lead(lead_obj.model_dump())

            # Use the newly created lead's default state
            lead = lead_obj.model_dump()

        # --------------------------------------------------
        # 2. Get or create conversation
        # --------------------------------------------------

        conversation = get_conversation(conversation_id)

        if not conversation:
            conversation_obj = Conversation(
                conversation_id=conversation_id,
                lead_id=lead_id,
                channel=channel,
                sender_id=sender_id,
            )

            create_conversation(conversation_obj.model_dump())

        # --------------------------------------------------
        # 3. Save inbound message FIRST
        # --------------------------------------------------

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

        print("WHATSAPP MESSAGE SAVED TO MONGODB")
        print("Lead:", lead_id)
        print("Conversation:", conversation_id)
        print("Message:", text)

        # --------------------------------------------------
        # 4. Qualification
        # --------------------------------------------------

        qualification = qualify_lead(
            conversation_id=conversation_id,
            new_message=text,
        )

        print("WHATSAPP QUALIFICATION:", qualification)

        # --------------------------------------------------
        # 5. Human takeover check
        # --------------------------------------------------

        if not lead.get("automation_enabled", True):
            print("AUTOMATION DISABLED - HUMAN TAKEOVER")

            return {
                "status": "received",
                "saved": True,
                "lead_id": lead_id,
                "conversation_id": conversation_id,
                "automation": "disabled",
            }

        # --------------------------------------------------
        # 6. Determine response
        # --------------------------------------------------

        if qualification["qualification"]["status"] == "needs_information":

            reply = qualification["qualification"]["follow_up"]

        else:

            reply = generate_reply(
                conversation_id=conversation_id,
                new_message=text,
            )

        # --------------------------------------------------
        # 7. Send response
        # --------------------------------------------------

        # IMPORTANT:
        # WhatsApp outbound is currently blocked by the
        # Twilio Sandbox/trial restriction.

        # adapter = WhatsAppAdapter()
        # adapter.send(
        #     recipient=sender_id,
        #     message=reply,
        # )

        print("WHATSAPP REPLY GENERATED:", reply)

        return {
            "status": "received",
            "saved": True,
            "lead_id": lead_id,
            "conversation_id": conversation_id,
            "qualification": qualification,
            "reply": reply,
        }

    except Exception as e:

        print("WhatsApp persistence error:", str(e))

        return {
            "status": "received",
            "saved": False,
            "error": str(e),
        }