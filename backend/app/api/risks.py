from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, delete, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.risk_finding import RiskFinding, RiskStatus
from app.models.log_event import LogEvent
from app.models.config_item import ConfigItem
from app.models.material import Material
from app.models.project import Project

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


class RiskPatchRequest(BaseModel):
    status: Optional[str] = None
    note: Optional[str] = None


@router.patch("/risks/{risk_id}", response_model=RiskFindingRead)
async def patch_risk(
    risk_id: int,
    payload: RiskPatchRequest,
    db: AsyncSession = Depends(get_db),
):
    """Compat alias: PATCH /risks/{id} (frontend calls this). Also accepts status field."""
    stmt = select(RiskFinding).where(RiskFinding.id == risk_id)
    res = await db.execute(stmt)
    r = res.scalar_one_or_none()
    if r is None:
        raise HTTPException(status_code=404, detail="Risk finding not found")

    if payload.status:
        st = payload.status.lower()
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


# ===================== Project-level Audit Endpoints ==========================
# These are the core 配置核查 and 流量审核 features.


class ConfigAuditSummary(BaseModel):
    project_id: int
    project_name: Optional[str] = None
    total_materials_scanned: int
    total_config_items: int
    risk_items_count: int
    high_risk_count: int
    medium_risk_count: int
    low_risk_count: int
    findings: list
    by_section: Dict[str, Any]
    by_device: Dict[str, Any]


@router.post("/projects/{project_id}/audit/config", response_model=ConfigAuditSummary)
async def project_config_audit(
    project_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Run project-level 配置核查 (Configuration Audit).

    Aggregates config items across all materials of the project, runs the risk engine,
    and returns a structured audit summary with findings grouped by section / device.
    """
    p_stmt = select(Project).where(Project.id == project_id)
    p_res = await db.execute(p_stmt)
    project = p_res.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    # Collect context
    mat_stmt = select(Material.id, Material.file_name, Material.device_name).where(
        Material.project_id == project_id
    )
    mat_res = await db.execute(mat_stmt)
    mat_rows = mat_res.all()
    material_ids = [row[0] for row in mat_rows]
    total_materials = len(material_ids)

    config_trees: List[Dict[str, Any]] = []
    all_ci_ids: List[int] = []
    by_section: Dict[str, Dict[str, Any]] = {}
    by_device: Dict[str, Dict[str, Any]] = {}

    for mid, _fname, _dname in mat_rows:
        ci_stmt = select(ConfigItem).where(ConfigItem.material_id == mid).order_by(ConfigItem.id)
        ci_res = await db.execute(ci_stmt)
        cis = list(ci_res.scalars().all())
        if not cis:
            continue

        sections_map: Dict[tuple, List[Any]] = {}
        device_name = None
        for ci in cis:
            if device_name is None and ci.device_name:
                device_name = ci.device_name
            all_ci_ids.append(ci.id)
            # Aggregate by section
            s_label = f"{ci.section_type or 'root'}"
            if ci.section_name:
                s_label += f":{ci.section_name}"
            sec_agg = by_section.setdefault(s_label, {"total": 0, "risk": 0})
            sec_agg["total"] += 1
            if ci.is_risk:
                sec_agg["risk"] += 1
            # Aggregate by device
            dev_key = ci.device_name or f"material-{mid}"
            dev_agg = by_device.setdefault(dev_key, {"total": 0, "risk": 0})
            dev_agg["total"] += 1
            if ci.is_risk:
                dev_agg["risk"] += 1
            # Build sections
            key = (ci.section_type or "", ci.section_name or "")
            sections_map.setdefault(key, []).append({
                "id": ci.id,
                "line_no": ci.line_no,
                "raw_line": ci.raw_line,
                "key": ci.key,
                "value": ci.value,
                "indent_level": ci.indent_level or 0,
                "annotation": ci.annotation,
                "doc_ref": ci.doc_ref,
                "is_risk": bool(ci.is_risk),
                "risk_level": ci.risk_level.value if ci.risk_level and hasattr(ci.risk_level, "value") else str(ci.risk_level or "none"),
            })
        sections = []
        for (st, sn), items in sections_map.items():
            sections.append({"section_type": st, "section_name": sn, "items": items})
        config_trees.append({
            "material_id": mid,
            "device_name": device_name,
            "sections": sections,
        })

    # Run config analysis via engine
    ctx = {
        "project_id": project_id,
        "material_ids": material_ids,
        "config_trees": config_trees,
        "log_events": [],
        "traffic_events": [],
    }
    findings = _risk_engine.analyze_all(ctx)

    # Count risk items
    total_items = len(all_ci_ids)
    from app.models.risk_finding import Severity

    # Risk counts from findings
    high_risk = sum(1 for f in findings if (f.get("severity") or "").lower() in ("high", "critical"))
    medium_risk = sum(1 for f in findings if (f.get("severity") or "").lower() == "medium")
    low_risk = sum(1 for f in findings if (f.get("severity") or "").lower() in ("low", "info"))

    # Also count from ConfigItem is_risk flag
    risk_stmt = (
        select(
            func.count().label("c"),
        )
        .where(ConfigItem.project_id == project_id, ConfigItem.is_risk.is_(True))
    )
    risk_res = await db.execute(risk_stmt)
    risk_items_count = int(risk_res.scalar_one() or 0)

    # Persist refreshed findings (delete per-project + re-insert)
    await db.execute(delete(RiskFinding).where(
        RiskFinding.project_id == project_id,
        RiskFinding.category == "config",
    ))
    sev_map = {
        "high": Severity.HIGH,
        "critical": Severity.CRITICAL,
        "medium": Severity.MEDIUM,
        "low": Severity.LOW,
        "info": Severity.LOW,
    }
    config_findings = [
        f for f in findings
        if (f.get("category") or "") in ("config", "config_security", "compliance", "")
    ]
    inserted_reads = []
    for f in config_findings:
        sev = sev_map.get((f.get("severity") or "").lower(), Severity.MEDIUM)
        rf = RiskFinding(
            project_id=project_id,
            material_id=None,
            risk_code=f.get("risk_code", "CFG-AUDIT"),
            severity=sev,
            category=f.get("category", "config"),
            description=f.get("description"),
            source_ref=f.get("source_ref"),
            remediation_cmd=f.get("remediation_cmd"),
            standard_ref=f.get("standard_ref"),
            status=RiskStatus.OPEN,
        )
        db.add(rf)
        await db.flush()
        await db.refresh(rf)
        inserted_reads.append(_to_read(rf))
    await db.commit()

    return ConfigAuditSummary(
        project_id=project_id,
        project_name=project.name,
        total_materials_scanned=total_materials,
        total_config_items=total_items,
        risk_items_count=risk_items_count,
        high_risk_count=high_risk,
        medium_risk_count=medium_risk,
        low_risk_count=low_risk,
        findings=inserted_reads,
        by_section=by_section,
        by_device=by_device,
    )


class TrafficAuditSummary(BaseModel):
    project_id: int
    project_name: Optional[str] = None
    total_materials_scanned: int
    total_events: int
    traffic_events: int
    logon_events: int
    command_events: int
    findings: list
    top_sources: List[Dict[str, Any]]
    top_targets: List[Dict[str, Any]]
    top_protocols: List[Dict[str, Any]]
    total_bytes: int


@router.post("/projects/{project_id}/audit/traffic", response_model=TrafficAuditSummary)
async def project_traffic_audit(
    project_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Run project-level 流量审核 (Traffic & Log Audit).

    Aggregates log/traffic events across all materials of the project, runs the risk engine
    for log + traffic anomaly detection, and returns a structured audit summary.
    """
    p_stmt = select(Project).where(Project.id == project_id)
    p_res = await db.execute(p_stmt)
    project = p_res.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    mat_stmt = select(Material.id, Material.file_name, Material.device_name).where(
        Material.project_id == project_id
    )
    mat_res = await db.execute(mat_stmt)
    mat_rows = mat_res.all()
    material_ids = [row[0] for row in mat_rows]
    total_materials = len(material_ids)

    log_events: List[Dict[str, Any]] = []
    src_counter: Dict[str, int] = {}
    tgt_counter: Dict[str, int] = {}
    proto_counter: Dict[str, int] = {}
    total_bytes = 0
    traffic_events = 0
    logon_events = 0
    command_events = 0

    for mid, _fname, _dname in mat_rows:
        le_stmt = select(LogEvent).where(LogEvent.material_id == mid).order_by(LogEvent.id)
        le_res = await db.execute(le_stmt)
        for le in le_res.scalars().all():
            ev = {
                "timestamp": le.timestamp.isoformat() if le.timestamp else None,
                "event_type": le.event_type,
                "source_ip": le.source_ip,
                "target_ip": le.target_ip,
                "destination_port": le.destination_port,
                "_protocol": le._protocol,
                "_bytes": int(le._bytes or 0),
                "user": le.user,
                "device": le.device,
                "command": le.command,
                "result": le.result,
                "detail_json": le.detail_json,
                "raw_line": le.raw_line,
                "line_no": le.line_no,
            }
            log_events.append(ev)
            # Categorize
            et = (le.event_type or "").lower()
            if et in ("traffic", "flow", "netflow", "firewall"):
                traffic_events += 1
                if le._protocol:
                    proto_counter[le._protocol] = proto_counter.get(le._protocol, 0) + 1
            elif et in ("login", "logon", "logout", "auth"):
                logon_events += 1
            elif et in ("command", "exec", "configuration"):
                command_events += 1
            # IP counters
            if le.source_ip:
                src_counter[le.source_ip] = src_counter.get(le.source_ip, 0) + 1
            if le.target_ip:
                tgt_counter[le.target_ip] = tgt_counter.get(le.target_ip, 0) + 1
            # bytes
            try:
                total_bytes += int(le._bytes or 0)
            except Exception:
                pass

    total_events = len(log_events)

    # Risk engine analysis
    ctx = {
        "project_id": project_id,
        "material_ids": material_ids,
        "config_trees": [],
        "log_events": log_events,
        "traffic_events": [ev for ev in log_events if ev.get("event_type") and ev["event_type"].lower() in ("traffic", "flow", "netflow", "firewall")] or log_events,
    }
    findings = _risk_engine.analyze_all(ctx)

    # Persist refreshed findings (log/traffic category)
    await db.execute(delete(RiskFinding).where(
        RiskFinding.project_id == project_id,
        RiskFinding.category.in_(["log", "log_audit", "traffic", "traffic_anomaly", "compliance"]),
    ))
    from app.models.risk_finding import Severity
    sev_map = {
        "high": Severity.HIGH,
        "critical": Severity.CRITICAL,
        "medium": Severity.MEDIUM,
        "low": Severity.LOW,
        "info": Severity.LOW,
    }
    kept_categories = {"log", "log_audit", "traffic", "traffic_anomaly", "compliance", None, ""}
    inserted_reads = []
    for f in findings:
        if (f.get("category") or "") not in kept_categories and (f.get("category") or "") != "":
            continue
        sev = sev_map.get((f.get("severity") or "").lower(), Severity.MEDIUM)
        rf = RiskFinding(
            project_id=project_id,
            material_id=None,
            risk_code=f.get("risk_code", "TRF-AUDIT"),
            severity=sev,
            category=f.get("category") or "traffic",
            description=f.get("description"),
            source_ref=f.get("source_ref"),
            remediation_cmd=f.get("remediation_cmd"),
            standard_ref=f.get("standard_ref"),
            status=RiskStatus.OPEN,
        )
        db.add(rf)
        await db.flush()
        await db.refresh(rf)
        inserted_reads.append(_to_read(rf))
    await db.commit()

    # Sort top-N helpers
    def top_n(counter: Dict[str, int], n: int = 10):
        arr = [{"ip": k, "count": v} for k, v in counter.items()]
        arr.sort(key=lambda x: x["count"], reverse=True)
        return arr[:n]
    proto_top = [{"protocol": k, "count": v} for k, v in proto_counter.items()]
    proto_top.sort(key=lambda x: x["count"], reverse=True)

    return TrafficAuditSummary(
        project_id=project_id,
        project_name=project.name,
        total_materials_scanned=total_materials,
        total_events=total_events,
        traffic_events=traffic_events,
        logon_events=logon_events,
        command_events=command_events,
        findings=inserted_reads,
        top_sources=top_n(src_counter),
        top_targets=top_n(tgt_counter),
        top_protocols=proto_top[:10],
        total_bytes=total_bytes,
    )


@router.get("/projects/{project_id}/audit/summary")
async def project_audit_summary(
    project_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Lightweight audit summary endpoint (used by dashboard cards)."""
    p_stmt = select(Project).where(Project.id == project_id)
    p_res = await db.execute(p_stmt)
    project = p_res.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    mat_count_stmt = select(func.count()).select_from(Material).where(
        Material.project_id == project_id
    )
    mat_count = int((await db.execute(mat_count_stmt)).scalar_one() or 0)

    risk_stmt = (
        select(RiskFinding.severity, func.count().label("c"))
        .where(RiskFinding.project_id == project_id)
        .group_by(RiskFinding.severity)
    )
    risk_rows = (await db.execute(risk_stmt)).all()
    severity_counts: Dict[str, int] = {}
    total_risks = 0
    from app.models.risk_finding import Severity
    for sev, c in risk_rows:
        key = sev.value if hasattr(sev, "value") else str(sev)
        severity_counts[key] = int(c or 0)
        total_risks += int(c or 0)

    ci_stmt = select(func.count()).select_from(ConfigItem).where(
        ConfigItem.project_id == project_id
    )
    ci_count = int((await db.execute(ci_stmt)).scalar_one() or 0)
    ci_risk_stmt = select(func.count()).select_from(ConfigItem).where(
        ConfigItem.project_id == project_id, ConfigItem.is_risk.is_(True)
    )
    ci_risk_count = int((await db.execute(ci_risk_stmt)).scalar_one() or 0)

    le_stmt = select(func.count()).select_from(LogEvent).where(
        LogEvent.project_id == project_id
    )
    le_count = int((await db.execute(le_stmt)).scalar_one() or 0)

    return {
        "project_id": project_id,
        "project_name": project.name,
        "materials": mat_count,
        "total_risks": total_risks,
        "severity_counts": severity_counts,
        "config_items": ci_count,
        "config_risk_items": ci_risk_count,
        "log_events": le_count,
    }
