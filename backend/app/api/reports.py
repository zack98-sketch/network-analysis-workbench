import asyncio
import os
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.project import Project
from app.models.material import Material
from app.models.risk_finding import RiskFinding
from app.models.log_event import LogEvent
from app.models.config_item import ConfigItem
from app.models.topology import TopoNode, TopoEdge

from app.services.report_service import ReportService

router = APIRouter()
_report_service = ReportService()

_reports_store: List[Dict[str, Any]] = []


class ReportGenerateRequest(BaseModel):
    format: str = "html"
    title: Optional[str] = None
    include_risks: bool = True
    include_topology: bool = True
    include_logs: bool = False
    include_configs: bool = False
    template: Optional[str] = None


class ReportRead(BaseModel):
    id: int
    project_id: int
    format: str
    title: str
    file_name: str
    file_size: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ReportGenerateResponse(BaseModel):
    task_id: str
    project_id: int
    format: str
    status: str
    report_id: Optional[int] = None
    download_url: Optional[str] = None


class _ReportInStore:
    def __init__(self, rid: int, pid: int, fmt: str, title: str, file_name: str, file_size: int):
        self.id = rid
        self.project_id = pid
        self.format = fmt
        self.title = title
        self.file_name = file_name
        self.file_size = file_size
        self.created_at = datetime.now()


_next_report_id = 1000


def _next_id() -> int:
    global _next_report_id
    _next_report_id += 1
    return _next_report_id


def _sev_str(v) -> str:
    if v is None:
        return "medium"
    if hasattr(v, "value"):
        return str(v.value)
    return str(v)


def _status_str(v) -> str:
    if v is None:
        return "pending"
    if hasattr(v, "value"):
        return str(v.value)
    return str(v)


def _material_status_str(m) -> str:
    ps = getattr(m, "parse_status", None)
    if ps is None:
        return "pending"
    if hasattr(ps, "value"):
        return str(ps.value)
    return str(ps)


async def _gather_project_data(project_id: int, db: AsyncSession, req: ReportGenerateRequest) -> Dict[str, Any]:
    proj_stmt = select(Project).where(Project.id == project_id)
    proj_res = await db.execute(proj_stmt)
    project = proj_res.scalar_one_or_none()

    mat_stmt = select(Material).where(Material.project_id == project_id).order_by(Material.created_at.desc())
    mat_res = await db.execute(mat_stmt)
    materials = list(mat_res.scalars().all())
    material_ids = [m.id for m in materials]

    materials_dicts = []
    for m in materials:
        materials_dicts.append({
            "id": m.id,
            "project_id": m.project_id,
            "file_name": m.file_name,
            "file_hash": m.file_hash,
            "file_path": m.file_path,
            "file_size": m.file_size,
            "file_type": m.file_type,
            "parser_type": m.parser_type,
            "parse_status": _material_status_str(m),
            "device_name": m.device_name,
            "vendor": m.vendor,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        })

    risks_dicts = []
    if req.include_risks:
        risk_stmt = select(RiskFinding).where(RiskFinding.project_id == project_id).order_by(
            RiskFinding.severity.desc(), RiskFinding.created_at.desc()
        )
        risk_res = await db.execute(risk_stmt)
        for r in risk_res.scalars().all():
            risks_dicts.append({
                "id": r.id,
                "project_id": r.project_id,
                "material_id": r.material_id,
                "risk_code": r.risk_code,
                "severity": _sev_str(r.severity),
                "category": r.category,
                "description": r.description,
                "source_ref": r.source_ref,
                "remediation_cmd": r.remediation_cmd,
                "standard_ref": r.standard_ref,
                "status": _status_str(r.status),
                "created_at": r.created_at.isoformat() if r.created_at else None,
            })

    log_events_dicts = []
    if req.include_logs and material_ids:
        log_stmt = (
            select(LogEvent)
            .where(LogEvent.material_id.in_(material_ids))
            .order_by(LogEvent.timestamp.asc().nullslast(), LogEvent.id.asc())
            .limit(200)
        )
        log_res = await db.execute(log_stmt)
        for le in log_res.scalars().all():
            log_events_dicts.append({
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

    config_trees_dicts = []
    if req.include_configs and material_ids:
        for mid in material_ids:
            ci_stmt = select(ConfigItem).where(ConfigItem.material_id == mid).order_by(ConfigItem.id)
            ci_res = await db.execute(ci_stmt)
            cis = list(ci_res.scalars().all())
            if not cis:
                continue
            sections_map: Dict[tuple, List[Any]] = {}
            device_name = None
            for ci in cis:
                if device_name is None:
                    device_name = ci.device_name
                key = (ci.section_type or "", ci.section_name or "")
                sections_map.setdefault(key, []).append({
                    "id": ci.id,
                    "line_no": ci.line_no,
                    "raw_line": ci.raw_line,
                    "key": ci.key,
                    "value": ci.value,
                    "indent_level": ci.indent_level,
                    "is_risk": ci.is_risk,
                    "risk_level": ci.risk_level.value if ci.risk_level else "none",
                })
            sections = []
            for (st, sn), items in sections_map.items():
                sections.append({"section_type": st, "section_name": sn, "items": items})
            config_trees_dicts.append({
                "material_id": mid,
                "device_name": device_name,
                "sections": sections,
            })

    topology_dict: Dict[str, Any] = {"nodes": [], "edges": []}
    if req.include_topology:
        n_stmt = select(TopoNode).where(TopoNode.project_id == project_id).order_by(TopoNode.id)
        n_res = await db.execute(n_stmt)
        for n in n_res.scalars().all():
            topology_dict["nodes"].append({
                "id": n.id,
                "node_type": n.node_type,
                "name": n.name,
                "ip_address": n.ip_address,
                "interface_desc": n.interface_desc,
                "pos_x": float(n.pos_x or 0.0),
                "pos_y": float(n.pos_y or 0.0),
                "source_material": n.source_material,
            })
        e_stmt = select(TopoEdge).where(TopoEdge.project_id == project_id).order_by(TopoEdge.id)
        e_res = await db.execute(e_stmt)
        for e in e_res.scalars().all():
            topology_dict["edges"].append({
                "id": e.id,
                "source_node": e.source_node,
                "target_node": e.target_node,
                "edge_type": e.edge_type,
                "bandwidth": e.bandwidth,
                "source_material": e.source_material,
            })

    return {
        "project": project,
        "materials": materials_dicts,
        "risks": risks_dicts,
        "log_events": log_events_dicts,
        "config_trees": config_trees_dicts,
        "topology": topology_dict,
    }


async def _do_generate(project_id: int, req: ReportGenerateRequest, db: AsyncSession):
    global _reports_store
    data = await _gather_project_data(project_id, db, req)

    fmt = (req.format or "html").lower()

    if fmt in ("html", "htm"):
        html = _report_service.generate_html(
            project=data["project"],
            materials=data["materials"],
            risks=data["risks"],
            config_trees=data["config_trees"],
            topology=data["topology"],
            events=data["log_events"],
            title=req.title,
        )
        content_bytes = html.encode("utf-8")
        saved = _report_service.save_report(project_id, "html", content_bytes)
    elif fmt in ("md", "markdown"):
        md = _report_service.generate_markdown(
            project=data["project"],
            materials=data["materials"],
            risks=data["risks"],
            events=data["log_events"],
            title=req.title,
        )
        content_bytes = md.encode("utf-8")
        saved = _report_service.save_report(project_id, "md", content_bytes)
    elif fmt == "pdf":
        html = _report_service.generate_html(
            project=data["project"],
            materials=data["materials"],
            risks=data["risks"],
            config_trees=data["config_trees"],
            topology=data["topology"],
            events=data["log_events"],
            title=req.title,
        )
        content_bytes = _report_service.generate_pdf(html)
        saved = _report_service.save_report(project_id, "pdf", content_bytes)
    else:
        raise ValueError(f"Unsupported format: {fmt}")

    rid = _next_id()
    report_meta = {
        "id": rid,
        "project_id": project_id,
        "format": saved.get("format", fmt),
        "title": req.title or f"Report project {project_id}",
        "file_name": saved.get("file_name"),
        "file_path": saved.get("file_path"),
        "file_size": saved.get("file_size"),
        "download_url": saved.get("download_url"),
        "created_at": datetime.now(),
    }
    _reports_store.append(report_meta)
    return report_meta


@router.post("/projects/{project_id}/reports/generate", response_model=ReportGenerateResponse)
async def generate_report(
    project_id: int,
    payload: ReportGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    proj_stmt = select(Project.id).where(Project.id == project_id)
    proj_res = await db.execute(proj_stmt)
    if proj_res.scalar() is None:
        raise HTTPException(status_code=404, detail="Project not found")

    task_id = f"report-{project_id}-{int(datetime.now().timestamp())}"
    fmt = (payload.format or "html").lower()

    try:
        meta = await _do_generate(project_id, payload, db)
        return ReportGenerateResponse(
            task_id=task_id,
            project_id=project_id,
            format=fmt,
            status="completed",
            report_id=meta["id"],
            download_url=meta.get("download_url"),
        )
    except Exception as exc:
        return ReportGenerateResponse(
            task_id=task_id,
            project_id=project_id,
            format=fmt,
            status=f"failed: {exc}",
            report_id=None,
            download_url=None,
        )


@router.get("/projects/{project_id}/reports", response_model=list[ReportRead])
async def list_reports(project_id: int, db: AsyncSession = Depends(get_db)):
    result = []
    for meta in _reports_store:
        if meta.get("project_id") != project_id:
            continue
        result.append(ReportRead(
            id=int(meta["id"]),
            project_id=int(meta["project_id"]),
            format=str(meta.get("format", "")),
            title=str(meta.get("title", "")),
            file_name=str(meta.get("file_name", "")),
            file_size=meta.get("file_size"),
            created_at=meta.get("created_at") or datetime.now(),
        ))
    result.sort(key=lambda r: r.created_at, reverse=True)
    return result


@router.get("/reports/{report_id}/download")
async def download_report(report_id: int, db: AsyncSession = Depends(get_db)):
    target = None
    for meta in _reports_store:
        if int(meta.get("id")) == int(report_id):
            target = meta
            break
    if target is None:
        raise HTTPException(status_code=404, detail="Report not found")
    file_path = target.get("file_path")
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Report file missing on disk")
    fname = target.get("file_name") or f"report_{report_id}"
    return FileResponse(path=file_path, filename=fname)
