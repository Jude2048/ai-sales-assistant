from shared.gemini import generate_response
from shared.mongo import get_messages, update_lead
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

    # Get lead_id from conversation_id
    from shared.mongo import get_conversation

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

    return {
        "facts": facts,
        "qualification": result,
    }