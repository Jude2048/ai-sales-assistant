import os
from google import genai
import json


client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)


def generate_response(prompt: str) -> str:
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    return response.text


def extract_lead_facts(conversation: str) -> dict:
    prompt = f"""
You extract facts from a sales conversation.

Return ONLY valid JSON.

Extract these fields:

{{
    "need": string or null,
    "company_size": number or null,
    "budget": number or null,
    "service": string or null
}}

Rules:
- Only extract information explicitly stated by the customer.
- Never invent missing values.
- If information is missing, use null.
- Do not decide whether the lead is qualified.
- Do not assign a representative.
- Do not apply business policy.

Conversation:
{conversation}
"""

    response = client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents=prompt,
    )

    text = response.text.strip()

    # Handle accidental markdown code fences
    if text.startswith("```"):
        text = text.replace("```json", "")
        text = text.replace("```", "")
        text = text.strip()

    return json.loads(text)