import os
from google import genai
import json


client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)


def generate_response(prompt: str) -> str:
    response = client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents=prompt,
    )

    return response.text


def extract_lead_facts(conversation: str) -> dict:
    prompt = f"""
You extract factual information from a sales conversation.

Return ONLY valid JSON with exactly these fields:

{{
    "need": string or null,
    "company_size": number or null,
    "budget": number or null,
    "service": string or null
}}

Rules:
- Extract information explicitly stated by the customer.
- Do not invent missing information.
- "need" should contain the customer's stated business need.
- "company_size" should be the number of employees if stated.
- "budget" should be the stated numerical budget.
- For "service", map the customer's request to ONE of these exact supported services when applicable:
  "data analytics"
  "business intelligence"
  "dashboard development"
  "data strategy"
- If multiple services are mentioned, select the supported service that best matches the customer's request.
- If no supported service matches, use null.
- Do not decide qualification.
- Do not assign a representative.
- Do not apply business policy.
- When the customer provides a new value that conflicts with an earlier value,
  use the customer's latest explicitly stated value.
- The latest customer message has priority over earlier conversation history.
- Example: if the earlier budget was £10000 but the latest customer message says
  "I need your services for free", extract budget as 0.
- Do not preserve an older value when the customer explicitly changes it.

Customer conversation:
{conversation}
"""

    response = client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents=prompt,
    )

    text = response.text.strip()

    if text.startswith("```"):
        text = text.replace("```json", "").replace("```", "").strip()

    return json.loads(text)