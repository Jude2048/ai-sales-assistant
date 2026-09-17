import os
from datetime import datetime, timedelta, timezone

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


class GoogleCalendarAdapter:

    def __init__(self, google_tokens_collection):
        self.google_tokens = google_tokens_collection

    def _get_service(self):
        token_doc = self.google_tokens.find_one({
            "provider": "gmail"
        })

        if not token_doc:
            raise RuntimeError("Google OAuth token not found")

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

        return build(
            "calendar",
            "v3",
            credentials=creds,
        )

    def get_availability(
        self,
        start_time: datetime,
        end_time: datetime,
    ):
        service = self._get_service()

        body = {
            "timeMin": start_time.isoformat(),
            "timeMax": end_time.isoformat(),
            "items": [
                {
                    "id": "primary"
                }
            ],
        }

        result = service.freebusy().query(
            body=body
        ).execute()

        busy = result["calendars"]["primary"].get("busy", [])

        return busy

    def is_available(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> bool:

        busy = self.get_availability(
            start_time,
            end_time,
        )

        return len(busy) == 0

    def create_event(
        self,
        summary: str,
        description: str,
        start_time: datetime,
        end_time: datetime,
        attendee_email: str | None = None,
    ):

        service = self._get_service()

        event = {
            "summary": summary,
            "description": description,
            "start": {
                "dateTime": start_time.isoformat(),
                "timeZone": "Europe/London",
            },
            "end": {
                "dateTime": end_time.isoformat(),
                "timeZone": "Europe/London",
            },
        }

        if attendee_email:
            event["attendees"] = [
                {
                    "email": attendee_email
                }
            ]

        return service.events().insert(
            calendarId="primary",
            body=event,
            sendUpdates="all",
        ).execute()