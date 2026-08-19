from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum

from app.database import Base


class Severity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskStatus(str, enum.Enum):
    OPEN = "open"
    CONFIRMED = "confirmed"
    MITIGATED = "mitigated"
    DISMISSED = "dismissed"


class RiskFinding(Base):
    __tablename__ = "risk_findings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    material_id = Column(Integer, ForeignKey("materials.id", ondelete="SET NULL"), nullable=True, index=True)
    risk_code = Column(String(128), nullable=False, index=True)
    severity = Column(Enum(Severity), default=Severity.MEDIUM, index=True)
    category = Column(String(128), nullable=True, index=True)
    description = Column(Text, nullable=True)
    source_ref = Column(String(512), nullable=True)
    remediation_cmd = Column(Text, nullable=True)
    standard_ref = Column(String(255), nullable=True)
    status = Column(Enum(RiskStatus), default=RiskStatus.OPEN, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    project = relationship("Project")
    material = relationship("Material")
