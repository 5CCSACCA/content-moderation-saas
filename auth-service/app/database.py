import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://admin:changeme@postgres:5432/moderation"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI dependency that provides a database session per request
    and ensures it's closed afterwards, even if an error occurs."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()