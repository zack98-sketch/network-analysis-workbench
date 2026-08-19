from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, BigInteger, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum

from app.database import Base


class ParseStatus(str, enum.Enum):
    PENDING = "pending"
    PARSING = "parsing"
    SUCCESS = "success"
    FAILED = "failed"


class Material(Base):
    __tablename__ = "materials"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    file_name = Column(String(512), nullable=False)
    file_hash = Column(String(128), nullable=True, index=True)
    file_path = Column(Text, nullable=False)
    file_size = Column(BigInteger, nullable=True)
    file_type = Column(String(64), nullable=True, index=True)
    parser_type = Column(String(64), nullable=True, index=True)
    parse_status = Column(Enum(ParseStatus), default=ParseStatus.PENDING, index=True)
    device_name = Column(String(255), nullable=True, index=True)
    vendor = Column(String(128), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    project = relationship("Project")
