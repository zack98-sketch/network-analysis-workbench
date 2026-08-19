from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.log_event import LogEvent
from app.models.material import Material

router = APIRouter()


class LogEventRead(BaseModel):
    id: int
    material_id: int
    timestamp: Optional[datetime] = None
    event_type: Optional[str] = None
    source_ip: Optional[str] = None
    target_ip: Optional[str] = None
    user: Optional[str] = None
    device: Optional[str] = None
    command: Optional[str] = None
    result: Optional[str] = None
    detail_json: Optional[dict] = None
    raw_line: Optional[str] = None
    line_no: Optional[int] = None

    class Config:
        from_attributes = True


class PaginatedLogs(BaseModel):
    items: list[LogEventRead]
    total: int
    page: int
    page_size: int


def _to_read(le: LogEvent) -> LogEventRead:
    return LogEventRead(
        id=le.id,
        material_id=le.material_id,
        timestamp=le.timestamp,
        event_type=le.event_type,
        source_ip=le.source_ip,
        target_ip=le.target_ip,
        user=le.user,
        device=le.device,
        command=le.command,
        result=le.result,
        detail_json=le.detail_json,
        raw_line=le.raw_line,
        line_no=le.line_no,
    )


@router.get("/materials/{material_id}/events", response_model=PaginatedLogs)
async def list_material_events(
    material_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    event_type: Optional[str] = Query(None),
    source_ip: Optional[str] = Query(None),
    target_ip: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    where_clauses = [LogEvent.material_id == material_id]
    if event_type:
        where_clauses.append(LogEvent.event_type == event_type)
    if source_ip:
        where_clauses.append(LogEvent.source_ip == source_ip)
    if target_ip:
        where_clauses.append(LogEvent.target_ip == target_ip)

    total_stmt = select(func.count(LogEvent.id)).where(and_(*where_clauses))
    total_res = await db.execute(total_stmt)
    total = total_res.scalar() or 0

    stmt = (
        select(LogEvent)
        .where(and_(*where_clauses))
        .order_by(LogEvent.timestamp.asc().nullslast(), LogEvent.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    res = await db.execute(stmt)
    items = [_to_read(le) for le in res.scalars().all()]

    return PaginatedLogs(items=items, total=total, page=page, page_size=page_size)


@router.get("/projects/{project_id}/logs/timeline")
async def get_logs_timeline(
    project_id: int,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    bucket: str = Query("hour", pattern="^(minute|hour|day)$"),
    db: AsyncSession = Depends(get_db),
):
    mat_stmt = select(Material.id).where(Material.project_id == project_id)
    mat_res = await db.execute(mat_stmt)
    material_ids = [row[0] for row in mat_res.all()] or [-1]

    where_clauses = [LogEvent.material_id.in_(material_ids)]
    if start:
        where_clauses.append(LogEvent.timestamp >= start)
    if end:
        where_clauses.append(LogEvent.timestamp <= end)

    stmt = select(LogEvent).where(and_(*where_clauses)).order_by(LogEvent.timestamp.asc().nullslast())
    res = await db.execute(stmt)
    events = list(res.scalars().all())

    buckets: Dict[str, Dict[str, Any]] = {}
    for ev in events:
        if not ev.timestamp:
            continue
        ts = ev.timestamp
        if bucket == "minute":
            key = ts.strftime("%Y-%m-%d %H:%M")
        elif bucket == "day":
            key = ts.strftime("%Y-%m-%d")
        else:
            key = ts.strftime("%Y-%m-%d %H:00")
        if key not in buckets:
            buckets[key] = {"time": key, "count": 0, "by_type": {}}
        buckets[key]["count"] += 1
        et = ev.event_type or "other"
        buckets[key]["by_type"][et] = buckets[key]["by_type"].get(et, 0) + 1

    sorted_buckets = [buckets[k] for k in sorted(buckets.keys())]
    return {"project_id": project_id, "bucket": bucket, "buckets": sorted_buckets}


@router.get("/projects/{project_id}/logs/correlation")
async def get_logs_correlation(
    project_id: int,
    by: str = Query("user", pattern="^(user|device|source_ip|target_ip|event_type)$"),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    mat_stmt = select(Material.id).where(Material.project_id == project_id)
    mat_res = await db.execute(mat_stmt)
    material_ids = [row[0] for row in mat_res.all()] or [-1]

    col_map = {
        "user": LogEvent.user,
        "device": LogEvent.device,
        "source_ip": LogEvent.source_ip,
        "target_ip": LogEvent.target_ip,
        "event_type": LogEvent.event_type,
    }
    col = col_map[by]

    stmt = (
        select(col, func.count(LogEvent.id).label("cnt"))
        .where(LogEvent.material_id.in_(material_ids))
        .where(col.isnot(None))
        .group_by(col)
        .order_by(func.count(LogEvent.id).desc())
        .limit(limit)
    )
    res = await db.execute(stmt)
    rows = res.all()

    correlations = []
    for row in rows:
        correlations.append({"key": row[0], "value": row[0], "count": int(row[1])})

    return {"project_id": project_id, "by": by, "correlations": correlations}
