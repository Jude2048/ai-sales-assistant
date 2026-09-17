import os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from email.mime.text import MIMEText
import base64


class GmailAdapter:

    def __init__(self, google_tokens_collection):
        self.google_tokens = google_tokens_collection

    def _get_service(self):
        token_doc = self.google_tokens.find_one({"provider": "gmail"})

        print("GMAIL TOKEN FIELDS:", list(token_doc.keys()) if token_doc else None)

        if not token_doc:
            raise RuntimeError("Gmail OAuth token not found")

        creds = Credentials(
            token_doc["access_token"],
            refresh_token=token_doc["refresh_token"],
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.getenv("GOOGLE_CLIENT_ID"),
            client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
            scopes=["https://www.googleapis.com/auth/gmail.readonly", "https://www.googleapis.com/auth/gmail.send", ],
        )

        return build("gmail", "v1", credentials=creds)

    def send(self, recipient: str, subject: str, message: str):
        service = self._get_service()

        email = MIMEText(message)
        email["to"] = recipient
        email["subject"] = subject

        encoded_message = base64.urlsafe_b64encode(
            email.as_bytes()
        ).decode()

        result = service.users().messages().send(
            userId="me",
            body={"raw": encoded_message},
        ).execute()

        print("GMAIL MESSAGE SENT:", result["id"])

        return {
            "provider_message_id": result["id"],
            "status": "sent",
        }