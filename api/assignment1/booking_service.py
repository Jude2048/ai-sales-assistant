from datetime import datetime, timedelta

from api.assignment1.calendar_adapter import GoogleCalendarAdapter
from shared.mongo import (
    get_booking_by_idempotency_key,
    create_booking,
)

def get_available_slots(calendar, date):
    slots = []

    for hour in range(9, 17):
        start_time = datetime(
            date.year,
            date.month,
            date.day,
            hour,
            0,
            tzinfo=date.tzinfo,
        )
        end_time = start_time + timedelta(minutes=30)

        if calendar.is_available(start_time, end_time):
            slots.append(start_time)

    return slots[:3]

def book_meeting(
    lead_id: str,
    conversation_id: str,
    attendee_email: str,
    start_time: datetime,
    duration_minutes: int,
    google_tokens_collection,
):
    end_time = start_time + timedelta(minutes=duration_minutes)

    idempotency_key = (
        f"{lead_id}:{start_time.isoformat()}:{duration_minutes}"
    )

    # 1. Prevent duplicate booking
    existing = get_booking_by_idempotency_key(idempotency_key)

    if existing:
        return {
            "status": "already_booked",
            "booking": existing,
        }

    calendar = GoogleCalendarAdapter(
        google_tokens_collection
    )

    # 2. Check availability
    if not calendar.is_available(start_time, end_time):
        return {
            "status": "slot_unavailable",
            "message": "The selected slot is no longer available.",
        }

    # 3. Recheck immediately before booking
    if not calendar.is_available(start_time, end_time):
        return {
            "status": "slot_unavailable",
            "message": "The selected slot became unavailable.",
        }

    # 4. Create event
    event = calendar.create_event(
        summary="Sales consultation",
        description=f"Sales consultation for lead {lead_id}",
        start_time=start_time,
        end_time=end_time,
        attendee_email=attendee_email,
    )

    # 5. Persist booking
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

def confirm_booking(
    lead_id: str,
    conversation_id: str,
    attendee_email: str,
    start_time: datetime,
    google_tokens_collection,
):
    return book_meeting(
        lead_id=lead_id,
        conversation_id=conversation_id,
        attendee_email=attendee_email,
        start_time=start_time,
        duration_minutes=30,
        google_tokens_collection=google_tokens_collection,
    )