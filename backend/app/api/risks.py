from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.risk_finding import RiskFinding, RiskStatus
from app.models.log_event import LogEvent
from app.models.config_item import ConfigItem
from app.models.material import Material

from app.engines.risk_engine import RiskEngine

router = APIRouter()
_risk_engine = RiskEngine()


class RiskFindingRead(BaseModel):
    id: int
    project_id: int
    material_id: Optional[int] = None
    risk_code: str
    severity: str = "medium"
    category: Optional[str] = None
    description: Optional[str] = None
    source_ref: Optional[str] = None
    remediation_cmd: Optional[str] = None
    standard_ref: Optional[str] = None
    status: str = "open"
    created_at: datetime

    class Config:
        from_attributes = True


class RiskStatusPatch(BaseModel):
    status: str


def _sev_str(v) -> str:
    if v is None:
        return "medium"
    if hasattr(v, "value"):
        return str(v.value)
    return str(v)


def _status_str(v) -> str:
    if v is None:
        return "open"
    if hasattr(v, "value"):
        return str(v.value)
    return str(v)


def _to_read(r: RiskFinding) -> RiskFindingRead:
    return RiskFindingRead(
        id=r.id,
        project_id=r.project_id,
        material_id=r.material_id,
        risk_code=r.risk_code,
        severity=_sev_str(r.severity),
        category=r.category,
        description=r.description,
        source_ref=r.source_ref,
        remediation_cmd=r.remediation_cmd,
        standard_ref=r.standard_ref,
        status=_status_str(r.status),
        created_at=r.created_at,
    )


@router.get("/projects/{project_id}/risks", response_model=list[RiskFindingRead])
async def list_project_risks(
    project_id: int,
    severity: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    where_clauses = [RiskFinding.project_id == project_id]
    if severity:
        sev_lower = severity.lower()
        if sev_lower in ("critical", "high"):
            from app.models.risk_finding import Severity
            if sev_lower == "critical":
                where_clauses.append(RiskFinding.severity == Severity.CRITICAL)
            else:
                where_clauses.append(RiskFinding.severity == Severity.HIGH)
        elif sev_lower == "medium":
            from app.models.risk_finding import Severity
            where_clauses.append(RiskFinding.severity == Severity.MEDIUM)
        elif sev_lower in ("low", "info"):
            from app.models.risk_finding import Severity
            where_clauses.append(RiskFinding.severity == Severity.LOW)
    if category:
        where_clauses.append(RiskFinding.category == category)
    if status:
        st_lower = status.lower()
        if st_lower == "open":
            where_clauses.append(RiskFinding.status == RiskStatus.OPEN)
        elif st_lower == "confirmed":
            where_clauses.append(RiskFinding.status == RiskStatus.CONFIRMED)
        elif st_lower == "mitigated":
            where_clauses.append(RiskFinding.status == RiskStatus.MITIGATED)
        elif st_lower == "dismissed":
            where_clauses.append(RiskFinding.status == RiskStatus.DISMISSED)

    stmt = select(RiskFinding).where(and_(*where_clauses)).order_by(
        RiskFinding.severity.desc(), RiskFinding.created_at.desc()
    )
    res = await db.execute(stmt)
    return [_to_read(r) for r in res.scalars().all()]


@router.post("/projects/{project_id}/risks/recheck")
async def recheck_risks(project_id: int, db: AsyncSession = Depends(get_db)):
    mat_stmt = select(Material.id, Material.project_id).where(Material.project_id == project_id)
    mat_res = await db.execute(mat_stmt)
    material_ids = [row[0] for row in mat_res.all()]

    log_events: List[Dict[str, Any]] = []
    config_trees: List[Dict[str, Any]] = []

    scanned = 0
    for mid in material_ids:
        log_stmt = select(LogEvent).where(LogEvent.material_id == mid).order_by(LogEvent.id)
        log_res = await db.execute(log_stmt)
        les = list(log_res.scalars().all())
        for le in les:
            log_events.append({
                "timestamp": le.timestamp.isoformat() if le.timestamp else None,
                "event_type": le.event_type,
                "source_ip": le.source_ip,
                "target_ip": le.target_ip,
                "user": le.user,
                "device": le.device,
                "command": le.command,
                "result": le.result,
                "detail_json": le.detail_json,
                "raw_line": le.raw_line,
                "line_no": le.line_no,
            })

        ci_stmt = select(ConfigItem).where(ConfigItem.material_id == mid).order_by(ConfigItem.id)
        ci_res = await db.execute(ci_stmt)
        cis = list(ci_res.scalars().all())
        scanned += 1
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
                "annotation": ci.annotation,
                "doc_ref": ci.doc_ref,
                "is_risk": ci.is_risk,
                "risk_level": ci.risk_level.value if ci.risk_level else "none",
            })
        sections = []
        for (st, sn), items in sections_map.items():
            sections.append({"section_type": st, "section_name": sn, "items": items})
        config_trees.append({
            "material_id": mid,
            "device_name": device_name,
            "sections": sections,
        })

    project_ctx = {
        "project_id": project_id,
        "material_ids": material_ids,
        "log_events": log_events,
        "config_trees": config_trees,
        "traffic_events": log_events,
    }

    findings = _risk_engine.analyze_all(project_ctx)

    await db.execute(delete(RiskFinding).where(RiskFinding.project_id == project_id))
    await db.flush()

    from app.models.risk_finding import Severity
    sev_map = {
        "high": Severity.HIGH,
        "critical": Severity.CRITICAL,
        "medium": Severity.MEDIUM,
        "low": Severity.LOW,
        "info": Severity.LOW,
    }
    inserted = []
    for f in findings:
        sev = sev_map.get((f.get("severity") or "").lower(), Severity.MEDIUM)
        rf = RiskFinding(
            project_id=project_id,
            material_id=None,
            risk_code=f.get("risk_code", "RISK-000"),
            severity=sev,
            category=f.get("category"),
            description=f.get("description"),
            source_ref=f.get("source_ref"),
            remediation_cmd=f.get("remediation_cmd"),
            standard_ref=f.get("standard_ref"),
            status=RiskStatus.OPEN,
        )
        db.add(rf)
        inserted.append(rf)
    await db.commit()
    for r in inserted:
        await db.refresh(r)

    return [_to_read(r) for r in inserted]


@router.patch("/risks/{risk_id}/status", response_model=RiskFindingRead)
async def patch_risk_status(
    risk_id: int,
    payload: RiskStatusPatch,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(RiskFinding).where(RiskFinding.id == risk_id)
    res = await db.execute(stmt)
    r = res.scalar_one_or_none()
    if r is None:
        raise HTTPException(status_code=404, detail="Risk finding not found")

    st = (payload.status or "").lower()
    if st == "open":
        r.status = RiskStatus.OPEN
    elif st == "confirmed":
        r.status = RiskStatus.CONFIRMED
    elif st == "mitigated":
        r.status = RiskStatus.MITIGATED
    elif st == "dismissed":
        r.status = RiskStatus.DISMISSED
    else:
        raise HTTPException(status_code=400, detail=f"Invalid status: {payload.status}")

    await db.commit()
    await db.refresh(r)
    return _to_read(r)
