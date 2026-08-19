from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, BigInteger
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database import Base


class LogEvent(Base):
    __tablename__ = "log_events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    material_id = Column(Integer, ForeignKey("materials.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=True, index=True)
    event_type = Column(String(128), nullable=True, index=True)
    source_ip = Column(String(64), nullable=True, index=True)
    target_ip = Column(String(64), nullable=True, index=True)
    user = Column(String(128), nullable=True, index=True)
    device = Column(String(255), nullable=True, index=True)
    command = Column(Text, nullable=True)
    result = Column(String(64), nullable=True, index=True)
    detail_json = Column(JSON, nullable=True)
    raw_line = Column(Text, nullable=True)
    line_no = Column(Integer, nullable=True)

    material = relationship("Material")
