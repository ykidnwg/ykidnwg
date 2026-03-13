"""
database/models.py – SQLAlchemy ORM models for job tracking and duplicate
detection.
"""

from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Text,
    BigInteger,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

from config import settings

Base = declarative_base()


class Job(Base):
    """Represents a single processing job (one Terabox link)."""

    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    link = Column(String(2048), nullable=False, unique=True, index=True)
    status = Column(String(32), default="PENDING")  # PENDING/RUNNING/SUCCESS/FAILED/DUPLICATE
    file_name = Column(String(512), nullable=True)
    file_size = Column(BigInteger, default=0)
    file_count = Column(Integer, default=0)
    share_link = Column(String(2048), nullable=True)
    category = Column(String(128), nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Job id={self.id} status={self.status} link={self.link[:60]}>"


class SeenFile(Base):
    """Tracks files already saved to cloud for duplicate detection."""

    __tablename__ = "seen_files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_name = Column(String(512), nullable=False, index=True)
    file_size = Column(BigInteger, default=0)
    cloud_path = Column(String(1024), nullable=True)
    share_link = Column(String(2048), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<SeenFile name={self.file_name}>"


def get_engine():
    return create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False,
    )


def init_db():
    """Create all tables if they don't exist."""
    engine = get_engine()
    Base.metadata.create_all(engine)
    return engine


def get_session():
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()
