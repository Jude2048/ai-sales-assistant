import os

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

router = APIRouter()

VERIFY_TOKEN = os.getenv("INSTAGRAM_VERIFY_TOKEN")


@router.get("/instagram", response_class=PlainTextResponse)
async def verify_instagram_webhook(
    hub_mode: str | None = None,
    hub_verify_token: str | None = None,
    hub_challenge: str | None = None,
):
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return hub_challenge or ""

    return "Verification failed"


@router.post("/instagram")
async def receive_instagram_webhook(request: Request):
    payload = await request.json()

    print("Instagram webhook received:")
    print(payload)

    return {"status": "received"}