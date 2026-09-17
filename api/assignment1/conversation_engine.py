from shared.gemini import generate_response
from shared.mongo import get_messages, update_lead, get_conversation    
from shared.gemini import generate_response, extract_lead_facts
from api.assignment1.policy import evaluate_lead

def extract_facts(conversation_id: str, new_message: str) -> dict:
    history = get_messages(conversation_id)

    conversation = []

    for msg in history:
        role = "Customer" if msg["direction"] == "inbound" else "Assistant"
        conversation.append(f"{role}: {msg['content']}")

    conversation.append(f"Customer: {new_message}")

    return extract_lead_facts(
        "\n".join(conversation)
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