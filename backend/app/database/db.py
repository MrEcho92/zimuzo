import logging
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up the SQLAlchemy engine and session
engine = create_engine(str(settings.get_database_url))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class for models
Base = declarative_base()


def get_db() -> Generator:
    logging.info("Creating a new database session")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
