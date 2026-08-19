from sqlalchemy import Column, Integer, String, Text, ForeignKey, Boolean, Enum
from sqlalchemy.orm import relationship
import enum

from app.database import Base


class RiskLevel(str, enum.Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ConfigItem(Base):
    __tablename__ = "config_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    material_id = Column(Integer, ForeignKey("materials.id", ondelete="CASCADE"), nullable=False, index=True)
    device_name = Column(String(255), nullable=True, index=True)
    section_type = Column(String(128), nullable=True, index=True)
    section_name = Column(String(255), nullable=True, index=True)
    line_no = Column(Integer, nullable=True)
    raw_line = Column(Text, nullable=True)
    key = Column(String(512), nullable=True, index=True)
    value = Column(Text, nullable=True)
    indent_level = Column(Integer, default=0)
    annotation = Column(Text, nullable=True)
    doc_ref = Column(String(512), nullable=True)
    is_risk = Column(Boolean, default=False, index=True)
    risk_level = Column(Enum(RiskLevel), default=RiskLevel.NONE, index=True)

    material = relationship("Material")
