from fastapi import FastAPI
from api.webhooks.instagram import router as instagram_router
from fastapi.responses import HTMLResponse
from api.webhooks.whatsapp import router as whatsapp_router
from fastapi.responses import HTMLResponse, RedirectResponse
    

app = FastAPI(title="AI Sales Assistant")

app.include_router(instagram_router, prefix="/webhooks")
app.include_router(whatsapp_router, prefix="/webhooks")

@app.get("/")
async def root():
    return {"status": "ok"}

@app.get("/auth/google/callback")
async def google_callback(code: str | None = None):
    if not code:
        return {"error": "Missing authorization code"}

    return {
        "status": "Google OAuth callback received",
        "code_received": True,
    }

@app.get("/privacy-policy", response_class=HTMLResponse)
async def privacy_policy():
    return """
    <html>
    <head><title>Privacy Policy</title></head>
    <body>
        <h1>Privacy Policy</h1>
        <p>This application is a test AI sales assistant created for development and evaluation.</p>
        <p>We use information received through connected messaging services only to demonstrate
        message handling, lead qualification, scheduling, and related application functionality.</p>
        <p>Test data is used only for this project and is not sold to third parties.</p>
        <p>For questions about this application, contact the developer through the project repository.</p>
    </body>
    </html>
    """