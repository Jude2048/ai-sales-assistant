from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/instagram")
async def verify_instagram_webhook(
    hub_mode: str | None = None,
    hub_verify_token: str | None = None,
    hub_challenge: str | None = None,
):
    return {"challenge": hub_challenge}


@router.post("/instagram")
async def receive_instagram_webhook(request: Request):
    payload = await request.json()

    print("Instagram webhook received:")
    print(payload)

    return {"status": "received"}