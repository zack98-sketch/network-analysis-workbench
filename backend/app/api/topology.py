from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, status, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.topology import TopoNode, TopoEdge
from app.models.material import Material
from app.models.log_event import LogEvent
from app.models.config_item import ConfigItem

from app.engines.topology_engine import TopologyEngine

router = APIRouter()
_topo_engine = TopologyEngine()


class TopoNodeRead(BaseModel):
    id: int
    project_id: int
    node_type: Optional[str] = None
    name: str
    ip_address: Optional[str] = None
    interface_desc: Optional[str] = None
    pos_x: float = 0.0
    pos_y: float = 0.0
    source_material: Optional[str] = None

    class Config:
        from_attributes = True


class TopoNodeCreate(BaseModel):
    node_type: Optional[str] = None
    name: str
    ip_address: Optional[str] = None
    interface_desc: Optional[str] = None
    pos_x: float = 0.0
    pos_y: float = 0.0
    source_material: Optional[str] = None


class TopoEdgeRead(BaseModel):
    id: int
    project_id: int
    source_node: int
    target_node: int
    edge_type: Optional[str] = None
    bandwidth: Optional[str] = None
    source_material: Optional[str] = None

    class Config:
        from_attributes = True


class TopoEdgeCreate(BaseModel):
    source_node: int
    target_node: int
    edge_type: Optional[str] = None
    bandwidth: Optional[str] = None
    source_material: Optional[str] = None


class TopologyResponse(BaseModel):
    project_id: int
    nodes: list[TopoNodeRead]
    edges: list[TopoEdgeRead]


class NodePositionUpdate(BaseModel):
    pos_x: float
    pos_y: float


class PositionsUpdate(BaseModel):
    positions: dict[int, NodePositionUpdate]


def _node_to_read(n: TopoNode) -> TopoNodeRead:
    return TopoNodeRead(
        id=n.id,
        project_id=n.project_id,
        node_type=n.node_type,
        name=n.name,
        ip_address=n.ip_address,
        interface_desc=n.interface_desc,
        pos_x=float(n.pos_x or 0.0),
        pos_y=float(n.pos_y or 0.0),
        source_material=n.source_material,
    )


def _edge_to_read(e: TopoEdge) -> TopoEdgeRead:
    return TopoEdgeRead(
        id=e.id,
        project_id=e.project_id,
        source_node=e.source_node,
        target_node=e.target_node,
        edge_type=e.edge_type,
        bandwidth=e.bandwidth,
        source_material=e.source_material,
    )


@router.get("/projects/{project_id}/topology", response_model=TopologyResponse)
async def get_topology(project_id: int, db: AsyncSession = Depends(get_db)):
    n_stmt = select(TopoNode).where(TopoNode.project_id == project_id).order_by(TopoNode.id)
    n_res = await db.execute(n_stmt)
    nodes = [_node_to_read(n) for n in n_res.scalars().all()]

    e_stmt = select(TopoEdge).where(TopoEdge.project_id == project_id).order_by(TopoEdge.id)
    e_res = await db.execute(e_stmt)
    edges = [_edge_to_read(e) for e in e_res.scalars().all()]

    return TopologyResponse(project_id=project_id, nodes=nodes, edges=edges)


@router.post(
    "/projects/{project_id}/topology/nodes",
    response_model=TopoNodeRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_node(
    project_id: int,
    payload: TopoNodeCreate,
    db: AsyncSession = Depends(get_db),
):
    n = TopoNode(
        project_id=project_id,
        node_type=payload.node_type,
        name=payload.name,
        ip_address=payload.ip_address,
        interface_desc=payload.interface_desc,
        pos_x=float(payload.pos_x or 0.0),
        pos_y=float(payload.pos_y or 0.0),
        source_material=payload.source_material,
    )
    db.add(n)
    await db.commit()
    await db.refresh(n)
    return _node_to_read(n)


@router.post(
    "/projects/{project_id}/topology/edges",
    response_model=TopoEdgeRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_edge(
    project_id: int,
    payload: TopoEdgeCreate,
    db: AsyncSession = Depends(get_db),
):
    src_stmt = select(TopoNode.id).where(TopoNode.project_id == project_id, TopoNode.id == payload.source_node)
    src_res = await db.execute(src_stmt)
    if src_res.scalar() is None:
        raise HTTPException(status_code=404, detail=f"source node {payload.source_node} not found")
    tgt_stmt = select(TopoNode.id).where(TopoNode.project_id == project_id, TopoNode.id == payload.target_node)
    tgt_res = await db.execute(tgt_stmt)
    if tgt_res.scalar() is None:
        raise HTTPException(status_code=404, detail=f"target node {payload.target_node} not found")

    e = TopoEdge(
        project_id=project_id,
        source_node=payload.source_node,
        target_node=payload.target_node,
        edge_type=payload.edge_type,
        bandwidth=payload.bandwidth,
        source_material=payload.source_material,
    )
    db.add(e)
    await db.commit()
    await db.refresh(e)
    return _edge_to_read(e)


@router.delete("/projects/{project_id}/topology/nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_node(project_id: int, node_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(TopoNode).where(TopoNode.project_id == project_id, TopoNode.id == node_id)
    res = await db.execute(stmt)
    n = res.scalar_one_or_none()
    if n is None:
        raise HTTPException(status_code=404, detail="Node not found")
    await db.execute(delete(TopoEdge).where(
        (TopoEdge.project_id == project_id) &
        ((TopoEdge.source_node == node_id) | (TopoEdge.target_node == node_id))
    ))
    await db.delete(n)
    await db.commit()
    return None


@router.delete("/projects/{project_id}/topology/edges/{edge_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_edge(project_id: int, edge_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(TopoEdge).where(TopoEdge.project_id == project_id, TopoEdge.id == edge_id)
    res = await db.execute(stmt)
    e = res.scalar_one_or_none()
    if e is None:
        raise HTTPException(status_code=404, detail="Edge not found")
    await db.delete(e)
    await db.commit()
    return None


@router.put("/projects/{project_id}/topology/positions")
async def update_positions(
    project_id: int,
    payload: PositionsUpdate,
    db: AsyncSession = Depends(get_db),
):
    updated = 0
    for node_id, pos in (payload.positions or {}).items():
        stmt = select(TopoNode).where(TopoNode.project_id == project_id, TopoNode.id == node_id)
        res = await db.execute(stmt)
        n = res.scalar_one_or_none()
        if n is None:
            continue
        n.pos_x = float(pos.pos_x)
        n.pos_y = float(pos.pos_y)
        updated += 1
    if updated:
        await db.commit()
    return {
        "project_id": project_id,
        "updated_count": updated,
    }


@router.post("/projects/{project_id}/topology/regenerate", response_model=TopologyResponse)
async def regenerate_topology(project_id: int, db: AsyncSession = Depends(get_db)):
    mat_stmt = select(Material.id, Material.parser_type, Material.device_name, Material.file_type).where(
        Material.project_id == project_id
    )
    mat_res = await db.execute(mat_stmt)
    materials = list(mat_res.all())

    merged = {"nodes": [], "edges": []}

    for mid, parser_type, dev_name, file_type in materials:
        category = (file_type or "").lower()
        parser = (parser_type or "").lower()

        if category == "config" or "/config" in parser or "vrp" in parser or "ios" in parser:
            ci_stmt = select(ConfigItem).where(ConfigItem.material_id == mid).order_by(ConfigItem.id)
            ci_res = await db.execute(ci_stmt)
            cis = list(ci_res.scalars().all())
            sections_map: Dict[tuple, List[Any]] = {}
            device_name = dev_name
            for ci in cis:
                if device_name is None:
                    device_name = ci.device_name
                key = (ci.section_type or "", ci.section_name or "")
                sections_map.setdefault(key, []).append({
                    "line_no": ci.line_no,
                    "raw_line": ci.raw_line,
                    "key": ci.key,
                    "value": ci.value,
                })
            sections = []
            for (st, sn), items in sections_map.items():
                sections.append({"section_type": st, "section_name": sn, "items": items})
            tree = {"material_id": mid, "device_name": device_name, "sections": sections}
            extract = _topo_engine.extract_from_config(tree)
            merged = _topo_engine.merge_topology(merged, extract)
        elif category == "log" or "/log" in parser:
            log_stmt = select(LogEvent).where(LogEvent.material_id == mid).order_by(LogEvent.id)
            log_res = await db.execute(log_stmt)
            events = []
            for le in log_res.scalars().all():
                events.append({
                    "timestamp": le.timestamp.isoformat() if le.timestamp else None,
                    "event_type": le.event_type,
                    "source_ip": le.source_ip,
                    "target_ip": le.target_ip,
                    "user": le.user,
                    "device": le.device,
                    "command": le.command,
                    "result": le.result,
                    "raw_line": le.raw_line,
                    "line_no": le.line_no,
                })
            if "structured_csv" in parser or (events and any(
                ev.get("event_type") in ("traffic", "permit", "deny") for ev in events
            )):
                extract = _topo_engine.extract_from_csv_traffic(events)
            else:
                extract = _topo_engine.extract_from_logs(events)
            merged = _topo_engine.merge_topology(merged, extract)

    merged["nodes"] = _topo_engine.assign_default_positions(merged["nodes"])

    await db.execute(delete(TopoEdge).where(TopoEdge.project_id == project_id))
    await db.execute(delete(TopoNode).where(TopoNode.project_id == project_id))
    await db.flush()

    id_rewrite: Dict[int, int] = {}
    for n in merged.get("nodes", []):
        new_node = TopoNode(
            project_id=project_id,
            node_type=n.get("node_type"),
            name=n.get("name"),
            ip_address=n.get("ip_address"),
            interface_desc=n.get("interface_desc"),
            pos_x=float(n.get("pos_x") or 0.0),
            pos_y=float(n.get("pos_y") or 0.0),
            source_material=n.get("source_material"),
        )
        db.add(new_node)
        await db.flush()
        await db.refresh(new_node)
        id_rewrite[n.get("id")] = new_node.id

    for e in merged.get("edges", []):
        old_src = e.get("source_node")
        old_tgt = e.get("target_node")
        new_src = id_rewrite.get(old_src, old_src)
        new_tgt = id_rewrite.get(old_tgt, old_tgt)
        if new_src is None or new_tgt is None:
            continue
        db.add(TopoEdge(
            project_id=project_id,
            source_node=int(new_src),
            target_node=int(new_tgt),
            edge_type=e.get("edge_type"),
            bandwidth=e.get("bandwidth"),
            source_material=e.get("source_material"),
        ))
    await db.commit()

    final_nodes_stmt = select(TopoNode).where(TopoNode.project_id == project_id).order_by(TopoNode.id)
    final_nodes_res = await db.execute(final_nodes_stmt)
    final_nodes = [_node_to_read(n) for n in final_nodes_res.scalars().all()]

    final_edges_stmt = select(TopoEdge).where(TopoEdge.project_id == project_id).order_by(TopoEdge.id)
    final_edges_res = await db.execute(final_edges_stmt)
    final_edges = [_edge_to_read(e) for e in final_edges_res.scalars().all()]

    return TopologyResponse(project_id=project_id, nodes=final_nodes, edges=final_edges)
