from fastapi import APIRouter, Request

router = APIRouter()


@router.post("/whatsapp")
async def receive_whatsapp_webhook(request: Request):
    form = await request.form()

    payload = dict(form)

    print("WhatsApp webhook received:")
    print(payload)

    return {"status": "received"}