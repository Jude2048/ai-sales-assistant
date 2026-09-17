import os
import json
from twilio.rest import Client


class WhatsAppAdapter:

    def __init__(self):
        self.client = Client(
            os.getenv("TWILIO_ACCOUNT_SID"),
            os.getenv("TWILIO_AUTH_TOKEN"),
        )
        self.from_number = os.getenv("TWILIO_WHATSAPP_FROM")

    def send(self, recipient: str, message: str):
        result = self.client.messages.create(
            from_=self.from_number,
            to=recipient,
            content_sid=os.getenv("TWILIO_CONTENT_SID"),
            content_variables=json.dumps({
                "1": "17 September 2026",
                "2": message,
            }),
        )

        print("WHATSAPP MESSAGE SENT:", result.sid)

        return {
            "provider_message_id": result.sid,
            "status": result.status,
        }