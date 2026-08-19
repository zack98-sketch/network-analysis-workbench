from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class DocIndex(Base):
    __tablename__ = "doc_index"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    material_id = Column(Integer, ForeignKey("materials.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(512), nullable=True, index=True)
    section_path = Column(String(1024), nullable=True)
    content_text = Column(Text, nullable=True)
    config_keywords = Column(String(1024), nullable=True, index=True)
    page_no = Column(Integer, nullable=True)

    project = relationship("Project")
    material = relationship("Material")
