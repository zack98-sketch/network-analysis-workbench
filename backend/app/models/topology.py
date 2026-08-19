from sqlalchemy import Column, Integer, String, Text, ForeignKey, Float
from sqlalchemy.orm import relationship

from app.database import Base


class TopoNode(Base):
    __tablename__ = "topo_nodes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    node_type = Column(String(64), nullable=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    ip_address = Column(String(128), nullable=True, index=True)
    interface_desc = Column(String(255), nullable=True)
    pos_x = Column(Float, default=0.0)
    pos_y = Column(Float, default=0.0)
    source_material = Column(String(512), nullable=True)

    project = relationship("Project")


class TopoEdge(Base):
    __tablename__ = "topo_edges"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    source_node = Column(Integer, ForeignKey("topo_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    target_node = Column(Integer, ForeignKey("topo_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    edge_type = Column(String(64), nullable=True)
    bandwidth = Column(String(64), nullable=True)
    source_material = Column(String(512), nullable=True)

    project = relationship("Project")
