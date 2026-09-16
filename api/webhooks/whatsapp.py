from fastapi import APIRouter, Request
from shared.mongo import (
    create_lead,
    create_conversation,
    create_message,
    get_lead,
    get_conversation,
)

from shared.schemas import Lead, Conversation, Message

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

        # Create lead if needed
        lead = get_lead(lead_id)

        if not lead:
            lead_obj = Lead(
                lead_id=lead_id,
                channel=channel,
                sender_id=sender_id,
            )
            create_lead(lead_obj.model_dump())

        # Create conversation if needed
        conversation = get_conversation(conversation_id)

        if not conversation:
            conversation_obj = Conversation(
                conversation_id=conversation_id,
                lead_id=lead_id,
                channel=channel,
                sender_id=sender_id,
            )
            create_conversation(conversation_obj.model_dump())

        # Save message
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

        return {
            "status": "received",
            "saved": True,
            "lead_id": lead_id,
            "conversation_id": conversation_id,
        }

    except Exception as e:
        print("WhatsApp persistence error:", str(e))

        return {
            "status": "received",
            "saved": False,
            "error": str(e),
        }