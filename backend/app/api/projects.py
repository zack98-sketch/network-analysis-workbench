from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.project import Project, ProjectStatus
from app.models.material import Material
from app.models.risk_finding import RiskFinding, Severity
from app.models.topology import TopoNode, TopoEdge
from app.models.log_event import LogEvent

router = APIRouter()


class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None
    status: str = "active"


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class ProjectRead(ProjectBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProjectSummary(BaseModel):
    project_id: int
    materials_count: int
    risks_count: int
    critical_risks: int
    high_risks: int
    medium_risks: int
    low_risks: int
    nodes_count: int
    edges_count: int
    log_events_count: int


def _status_enum(s: Optional[str]) -> ProjectStatus:
    if not s:
        return ProjectStatus.ACTIVE
    s_lower = s.lower()
    for e in ProjectStatus:
        if e.value == s_lower:
            return e
    return ProjectStatus.ACTIVE


def _to_read(p: Project) -> ProjectRead:
    return ProjectRead(
        id=p.id,
        name=p.name,
        description=p.description,
        status=p.status.value if hasattr(p.status, "value") else str(p.status),
        created_at=p.created_at.replace(tzinfo=None) if p.created_at else p.created_at,
        updated_at=p.updated_at.replace(tzinfo=None) if p.updated_at else p.updated_at,
    )


@router.get("/projects", response_model=list[ProjectRead])
async def list_projects(db: AsyncSession = Depends(get_db)):
    stmt = select(Project).order_by(Project.updated_at.desc())
    res = await db.execute(stmt)
    return [_to_read(p) for p in res.scalars().all()]


@router.post("/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(payload: ProjectCreate, db: AsyncSession = Depends(get_db)):
    p = Project(
        name=payload.name,
        description=payload.description,
        status=_status_enum(payload.status),
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return _to_read(p)


@router.get("/projects/{project_id}", response_model=ProjectRead)
async def get_project(project_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(Project).where(Project.id == project_id)
    res = await db.execute(stmt)
    p = res.scalar_one_or_none()
    if p is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return _to_read(p)


@router.put("/projects/{project_id}", response_model=ProjectRead)
async def update_project(project_id: int, payload: ProjectUpdate, db: AsyncSession = Depends(get_db)):
    stmt = select(Project).where(Project.id == project_id)
    res = await db.execute(stmt)
    p = res.scalar_one_or_none()
    if p is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if payload.name is not None:
        p.name = payload.name
    if payload.description is not None:
        p.description = payload.description
    if payload.status is not None:
        p.status = _status_enum(payload.status)
    await db.commit()
    await db.refresh(p)
    return _to_read(p)


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(Project).where(Project.id == project_id)
    res = await db.execute(stmt)
    p = res.scalar_one_or_none()
    if p is None:
        raise HTTPException(status_code=404, detail="Project not found")
    await db.delete(p)
    await db.commit()
    return None


@router.get("/projects/{project_id}/summary", response_model=ProjectSummary)
async def get_project_summary(project_id: int, db: AsyncSession = Depends(get_db)):
    # verify project exists
    p_stmt = select(Project.id).where(Project.id == project_id)
    p_res = await db.execute(p_stmt)
    if p_res.scalar() is None:
        raise HTTPException(status_code=404, detail="Project not found")

    mat_stmt = select(func.count(Material.id)).where(Material.project_id == project_id)
    materials_count = (await db.execute(mat_stmt)).scalar() or 0

    risk_stmt = select(func.count(RiskFinding.id)).where(RiskFinding.project_id == project_id)
    risks_count = (await db.execute(risk_stmt)).scalar() or 0

    critical_stmt = select(func.count(RiskFinding.id)).where(
        RiskFinding.project_id == project_id, RiskFinding.severity == Severity.CRITICAL
    )
    critical_risks = (await db.execute(critical_stmt)).scalar() or 0

    high_stmt = select(func.count(RiskFinding.id)).where(
        RiskFinding.project_id == project_id, RiskFinding.severity == Severity.HIGH
    )
    high_risks = (await db.execute(high_stmt)).scalar() or 0

    medium_stmt = select(func.count(RiskFinding.id)).where(
        RiskFinding.project_id == project_id, RiskFinding.severity == Severity.MEDIUM
    )
    medium_risks = (await db.execute(medium_stmt)).scalar() or 0

    low_stmt = select(func.count(RiskFinding.id)).where(
        RiskFinding.project_id == project_id, RiskFinding.severity == Severity.LOW
    )
    low_risks = (await db.execute(low_stmt)).scalar() or 0

    node_stmt = select(func.count(TopoNode.id)).where(TopoNode.project_id == project_id)
    nodes_count = (await db.execute(node_stmt)).scalar() or 0

    edge_stmt = select(func.count(TopoEdge.id)).where(TopoEdge.project_id == project_id)
    edges_count = (await db.execute(edge_stmt)).scalar() or 0

    log_stmt = select(func.count(LogEvent.id)).where(
        LogEvent.material_id.in_(
            select(Material.id).where(Material.project_id == project_id)
        )
    )
    log_events_count = (await db.execute(log_stmt)).scalar() or 0

    return ProjectSummary(
        project_id=project_id,
        materials_count=int(materials_count),
        risks_count=int(risks_count),
        critical_risks=int(critical_risks),
        high_risks=int(high_risks),
        medium_risks=int(medium_risks),
        low_risks=int(low_risks),
        nodes_count=int(nodes_count),
        edges_count=int(edges_count),
        log_events_count=int(log_events_count),
    )
