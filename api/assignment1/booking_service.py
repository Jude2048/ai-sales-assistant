from datetime import datetime, timedelta

from api.assignment1.calendar_adapter import GoogleCalendarAdapter
from shared.mongo import (
    get_booking_by_idempotency_key,
    create_booking,
)


def book_meeting(
    lead_id: str,
    conversation_id: str,
    attendee_email: str,
    start_time: datetime,
    duration_minutes: int,
    google_tokens_collection,
):

    end_time = start_time + timedelta(
        minutes=duration_minutes
    )

    idempotency_key = (
        f"{lead_id}:"
        f"{start_time.isoformat()}:"
        f"{duration_minutes}"
    )

    # -----------------------------------------
    # 1. Duplicate protection
    # -----------------------------------------

    existing = get_booking_by_idempotency_key(
        idempotency_key
    )

    if existing:
        return {
            "status": "already_booked",
            "booking": existing,
        }

    calendar = GoogleCalendarAdapter(
        google_tokens_collection
    )

    # -----------------------------------------
    # 2. Check availability
    # -----------------------------------------

    if not calendar.is_available(
        start_time,
        end_time,
    ):
        return {
            "status": "slot_unavailable",
            "message": "The selected slot is no longer available.",
        }

    # -----------------------------------------
    # 3. Recheck immediately before creation
    # -----------------------------------------

    if not calendar.is_available(
        start_time,
        end_time,
    ):
        return {
            "status": "slot_unavailable",
            "message": "The selected slot became unavailable.",
        }

    # -----------------------------------------
    # 4. Create calendar event
    # -----------------------------------------

    event = calendar.create_event(
        summary="Sales consultation",
        description=(
            f"Sales consultation for lead {lead_id}"
        ),
        start_time=start_time,
        end_time=end_time,
        attendee_email=attendee_email,
    )

    # -----------------------------------------
    # 5. Persist booking
    # -----------------------------------------

    booking = {
        "lead_id": lead_id,
        "conversation_id": conversation_id,
        "idempotency_key": idempotency_key,
        "calendar_event_id": event["id"],
        "status": "confirmed",
        "start_time": start_time,
        "end_time": end_time,
        "attendee_email": attendee_email,
        "created_at": datetime.utcnow(),
    }

    create_booking(booking)

    return {
        "status": "confirmed",
        "booking": booking,
        "calendar_event": event,
    }