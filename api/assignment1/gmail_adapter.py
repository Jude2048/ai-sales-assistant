import os
import base64
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from email.mime.text import MIMEText


class GmailAdapter:

    def __init__(self, google_tokens_collection):
        self.google_tokens = google_tokens_collection

    def _get_service(self):
        token_doc = self.google_tokens.find_one({"provider": "gmail"})

        if not token_doc:
            raise RuntimeError("Gmail OAuth token not found")

        creds = Credentials(
            token=None,
            refresh_token=token_doc["refresh_token"],
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.getenv("GOOGLE_CLIENT_ID"),
            client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
            scopes=[
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.send",
            ],
        )

        return build("gmail", "v1", credentials=creds)

    def send(
        self,
        recipient: str,
        subject: str,
        message: str,
        thread_id: str | None = None,
        in_reply_to: str | None = None,
    ):
        service = self._get_service()

        email = MIMEText(message)
        email["to"] = recipient
        email["subject"] = subject

        if in_reply_to:
            email["In-Reply-To"] = in_reply_to
            email["References"] = in_reply_to

        encoded_message = base64.urlsafe_b64encode(
            email.as_bytes()
        ).decode()

        body = {"raw": encoded_message}

        if thread_id:
            body["threadId"] = thread_id

        result = service.users().messages().send(
            userId="me",
            body=body,
        ).execute()

        print("GMAIL MESSAGE SENT:", result["id"])

        return {
            "provider_message_id": result["id"],
            "status": "sent",
            "thread_id": result.get("threadId"),
        }