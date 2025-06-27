from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from app.viber.webhooks import router as viber_router
from app.admin.routes import router as admin_router
from app.config import Settings
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Myanmar Link Customer Service Bot",
    version="1.0.0",
    description="Viber bot for Myanmar Link customer service"
)

# Load settings
settings = Settings()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Initialize templates
templates = Jinja2Templates(directory="app/admin/templates")

# Include routers
app.include_router(viber_router, prefix="/api/viber")
app.include_router(admin_router)

@app.get("/")
async def root():
    return {"message": "Myanmar Link Viber Bot is running!", "status": "active"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "mmlink-cs-bot"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
