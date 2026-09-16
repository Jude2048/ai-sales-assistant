from fastapi import FastAPI
from api.webhooks.instagram import router as instagram_router

app = FastAPI(title="AI Sales Assistant")

app.include_router(instagram_router, prefix="/webhooks")


@app.get("/")
async def root():
    return {"status": "ok"}
