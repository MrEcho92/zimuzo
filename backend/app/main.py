import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.database.db import engine, init_db
from app.routes.v1.routes import api_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database
    await init_db()
    logger.info("Database initialized")
    yield
    # Cleanup
    await engine.dispose()


app = FastAPI(title=settings.project_name, lifespan=lifespan)
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
