from shared.gemini import generate_response
from shared.mongo import get_messages, update_lead, get_conversation, google_tokens_collection  
from shared.gemini import generate_response, extract_lead_facts
from api.assignment1.policy import evaluate_lead
from datetime import datetime, timedelta
from api.assignment1.calendar_adapter import GoogleCalendarAdapter



def extract_facts(conversation_id: str, new_message: str) -> dict:
    history = get_messages(conversation_id)

    conversation = []

    for msg in history:
        role = "Customer" if msg["direction"] == "inbound" else "Assistant"
        conversation.append(f"{role}: {msg['content']}")

    conversation.append(f"Customer: {new_message}")
    conversation_text = "\n".join(conversation)
    return extract_lead_facts(
    conversation_text
)


def build_prompt(conversation_id: str, new_message: str) -> str:
    history = get_messages(conversation_id)

    conversation = []

    for msg in history:
        role = "Customer" if msg["direction"] == "inbound" else "Assistant"
        conversation.append(f"{role}: {msg['content']}")

    conversation.append(f"Customer: {new_message}")

    return f"""
You are a sales assistant.

Have a helpful, professional conversation with the customer.
Use the conversation history to maintain context.
Do not invent company policies, prices, staff members, availability,
or other facts that are not provided.

Conversation history:
{chr(10).join(conversation)}

Respond naturally to the customer's latest message.
"""


def generate_reply(conversation_id: str, new_message: str) -> str:
    prompt = build_prompt(conversation_id, new_message)
    return generate_response(prompt)

def qualify_lead(conversation_id: str, new_message: str) -> dict:
    facts = extract_facts(conversation_id, new_message)
    result = evaluate_lead(facts)

    if result["status"] == "qualified":
        slots = get_booking_slots()

        result["booking_slots"] = [
            slot.isoformat() for slot in slots
        ]

        if slots:
            result["slot_message"] = (
                "Great, your requirements qualify for a consultation. "
                "Here are the available times:\n\n"
                + "\n".join(
                    f"{i + 1}. {slot.strftime('%A, %d %B at %H:%M')}"
                    for i, slot in enumerate(slots)
                )
                + "\n\nPlease reply with the number of your preferred slot."
            )

    conversation = get_conversation(conversation_id)

    if conversation:
        update_lead(
            conversation["lead_id"],
            {
                "status": result["status"],
                "qualification": {
                    "status": result["status"],
                    "evidence": result["evidence"],
                },
                "assignment": {
                    "representative": result["representative"],
                    "reason": result["reason"],
                },
                "qualification_facts": facts,
            },
        )

        if result["status"] == "qualified" and result.get("booking_slots"):
            update_lead(
                conversation["lead_id"],
                {
                    "pending_booking": {
                        "slots": result["booking_slots"],
                        "status": "awaiting_selection",
                    }
                },
            )

        if result["status"] == "needs_information":
            result["follow_up"] = qualification_followup(result)

    return {
        "facts": facts,
        "qualification": result,
    }

def qualification_followup(qualification: dict) -> str:
    missing = qualification["missing_information"]

    questions = {
        "business need": "What is the main business problem or goal you want help with?",
        "company size": "Approximately how many employees does your company have?",
        "budget": "What budget range have you allocated for this project?",
    }

    parts = [
        questions[item]
        for item in missing
        if item in questions
    ]

    if not parts:
        return "Could you provide a little more information about your requirements?"

    return "To help me understand your requirements, could you tell me:\n\n" + "\n".join(
        f"- {part}" for part in parts
    )

def is_booking_confirmation(message: str) -> bool:
    text = message.lower().strip()

    confirmations = [
        "yes",
        "yes please",
        "confirm",
        "confirmed",
        "book it",
        "book that",
        "that works",
        "that time works",
    ]

    return text in confirmations

def get_booking_slots():
    calendar = GoogleCalendarAdapter(google_tokens_collection)

    now = datetime.now().astimezone()
    slots = []

    for day_offset in range(7):
        date = now.date() + timedelta(days=day_offset)

        for hour in range(9, 17):
            start_time = datetime(
                date.year,
                date.month,
                date.day,
                hour,
                0,
                tzinfo=now.tzinfo,
            )

            end_time = start_time + timedelta(minutes=30)

            if start_time <= now:
                continue

            if calendar.is_available(start_time, end_time):
                slots.append(start_time)

            if len(slots) >= 3:
                return slots

    return slots

def get_selected_booking_slot(lead: dict, message: str):
    pending = lead.get("pending_booking")

    if not pending or pending.get("status") != "awaiting_selection":
        return None

    slots = pending.get("slots", [])
    text = message.strip().lower()

    if text in ["1", "2", "3"]:
        index = int(text) - 1

        if index < len(slots):
            return slots[index]

    return None

def is_booking_confirmation(message: str) -> bool:
    text = message.lower().strip()

    return text in [
        "yes",
        "yes please",
        "confirm",
        "confirmed",
        "book it",
        "book that",
        "that works",
        "that time works",
    ]

    return text in confirmations