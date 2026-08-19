from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Enum, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class RuleType(str, enum.Enum):
    CONFIG = "config"
    LOG = "log"
    COMPLIANCE = "compliance"
    TRAFFIC = "traffic"
    CUSTOM = "custom"


class RuleSeverity(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class Rule(Base):
    __tablename__ = "rules"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    rule_type = Column(Enum(RuleType), default=RuleType.CUSTOM, index=True)
    severity = Column(Enum(RuleSeverity), default=RuleSeverity.WARNING, index=True)
    enabled = Column(Boolean, default=True, index=True)
    yaml_content = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    remediation = Column(Text, nullable=True)
    standard_ref = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    project = relationship("Project")
