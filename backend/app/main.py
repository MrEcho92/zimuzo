import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.contants import API_DOC_URL
from app.core.config import settings
from app.routes.v1.routes import api_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


app = FastAPI(title=settings.project_name, docs_url=API_DOC_URL)
app.include_router(api_router, prefix=settings.api_prefix)

# TODO: Update CORS settings for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "healthy"}
