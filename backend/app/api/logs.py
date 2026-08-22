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


# 流量事件类型：permit/deny/traffic 视为流量事件
_TRAFFIC_EVENT_TYPES = ("permit", "deny", "traffic")
# 操作事件类型
_OPERATION_EVENT_TYPES = ("command", "change", "auth", "connect", "disconnect")


def _extract_protocol(ev: LogEvent) -> Optional[str]:
    """从 LogEvent 提取协议：优先使用 _protocol 字段，其次从 detail_json 中查找。"""
    proto = getattr(ev, "_protocol", None)
    if proto:
        return str(proto)
    detail = ev.detail_json or {}
    if isinstance(detail, dict):
        for key in ("protocol", "proto", "protocol_name"):
            v = detail.get(key)
            if v is not None:
                return str(v)
    return None


def _extract_target_port(ev: LogEvent) -> Optional[str]:
    """从 LogEvent 提取目标端口：优先使用 destination_port 字段，其次从 detail_json 中查找。"""
    port = getattr(ev, "destination_port", None)
    if port is not None:
        return str(port)
    detail = ev.detail_json or {}
    if isinstance(detail, dict):
        for key in ("dest_port", "destination_port", "dport", "target_port"):
            v = detail.get(key)
            if v is not None:
                return str(v)
    return None


def _top_n(counter: Dict[str, int], limit: int) -> list:
    """对计数字典按计数倒序取前 N 个，返回 [(key, count), ...]。"""
    return sorted(counter.items(), key=lambda x: x[1], reverse=True)[:limit]


@router.get("/projects/{project_id}/logs/traffic")
async def get_logs_traffic(
    project_id: int,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    # 查询项目所有 material 的 LogEvent
    mat_stmt = select(Material.id).where(Material.project_id == project_id)
    mat_res = await db.execute(mat_stmt)
    material_ids = [row[0] for row in mat_res.all()] or [-1]

    # 仅统计流量相关事件
    stmt = (
        select(LogEvent)
        .where(LogEvent.material_id.in_(material_ids))
        .where(LogEvent.event_type.in_(_TRAFFIC_EVENT_TYPES))
        .order_by(LogEvent.timestamp.asc().nullslast(), LogEvent.id.asc())
    )
    res = await db.execute(stmt)
    events = list(res.scalars().all())

    permit_count = 0
    deny_count = 0
    source_ips: Dict[str, int] = {}
    target_ips: Dict[str, int] = {}
    target_ports: Dict[str, int] = {}
    protocols: Dict[str, int] = {}
    timeline_buckets: Dict[str, Dict[str, Any]] = {}

    # 五元组联合聚合：(src_ip, dst_ip, src_port, dst_port, protocol) -> 流统计
    five_tuple_flows: Dict[tuple, Dict[str, Any]] = {}
    # 行为分析：源 IP 扫描的目标端口集合
    src_port_scan: Dict[str, set] = {}
    # 上下行字节统计
    total_up_bytes = 0
    total_down_bytes = 0

    for ev in events:
        et = (ev.event_type or "").lower()
        if et == "permit":
            permit_count += 1
        elif et == "deny":
            deny_count += 1

        if ev.source_ip:
            source_ips[ev.source_ip] = source_ips.get(ev.source_ip, 0) + 1
        if ev.target_ip:
            target_ips[ev.target_ip] = target_ips.get(ev.target_ip, 0) + 1
        port = _extract_target_port(ev)
        if port:
            target_ports[port] = target_ports.get(port, 0) + 1
        proto = _extract_protocol(ev)
        if proto:
            protocols[proto] = protocols.get(proto, 0) + 1
        if ev.timestamp:
            key = ev.timestamp.strftime("%Y-%m-%d %H:00")
            if key not in timeline_buckets:
                timeline_buckets[key] = {"time": key, "permit": 0, "deny": 0}
            if et == "permit":
                timeline_buckets[key]["permit"] += 1
            elif et == "deny":
                timeline_buckets[key]["deny"] += 1

        # 五元组联合聚合
        src = ev.source_ip or "-"
        dst = ev.target_ip or "-"
        dst_port = port or "-"
        proto = proto or "-"
        src_port = None
        if ev.detail_json and isinstance(ev.detail_json, dict):
            src_port = ev.detail_json.get("src_port") or ev.detail_json.get("sport")
        src_port = src_port or "-"
        tuple_key = (src, dst, str(src_port), str(dst_port), proto)
        if tuple_key not in five_tuple_flows:
            five_tuple_flows[tuple_key] = {
                "src_ip": src if src != "-" else None,
                "dst_ip": dst if dst != "-" else None,
                "src_port": str(src_port) if src_port != "-" else None,
                "dst_port": str(dst_port) if dst_port != "-" else None,
                "protocol": proto if proto != "-" else None,
                "permit": 0,
                "deny": 0,
                "total": 0,
                "bytes": 0,
                "up_bytes": 0,
                "down_bytes": 0,
                "success": False,
            }
        flow = five_tuple_flows[tuple_key]
        flow["total"] += 1
        if et == "permit":
            flow["permit"] += 1
            flow["success"] = True
        elif et == "deny":
            flow["deny"] += 1
        # 字节统计（上下行）
        b = 0
        if ev.detail_json and isinstance(ev.detail_json, dict):
            b = int(ev.detail_json.get("bytes") or ev.detail_json.get("_bytes") or 0)
            total_up_bytes += int(ev.detail_json.get("tx_bytes") or 0)
            total_down_bytes += int(ev.detail_json.get("rx_bytes") or 0)
        flow["bytes"] += b
        flow["up_bytes"] += int((ev.detail_json or {}).get("tx_bytes", 0)) if isinstance(ev.detail_json, dict) else 0
        flow["down_bytes"] += int((ev.detail_json or {}).get("rx_bytes", 0)) if isinstance(ev.detail_json, dict) else 0

        # 端口扫描检测：单源 IP 命中多个不同目标端口
        if ev.source_ip and port:
            src_port_scan.setdefault(ev.source_ip, set()).add(port)

    timeline = [timeline_buckets[k] for k in sorted(timeline_buckets.keys())]

    # 行为分析：端口扫描、异常外联
    behaviors: List[Dict[str, Any]] = []
    for src_ip, ports in src_port_scan.items():
        if len(ports) >= 10:
            behaviors.append({
                "type": "port_scan",
                "severity": "high",
                "description": f"源 IP {src_ip} 扫描了 {len(ports)} 个不同目标端口，疑似端口扫描",
                "src_ip": src_ip,
                "port_count": len(ports),
            })

    # 高频被拒流（疑似攻击）
    for tuple_key, flow in five_tuple_flows.items():
        if flow["deny"] >= 20:
            behaviors.append({
                "type": "frequent_deny",
                "severity": "medium",
                "description": f"五元组流被拒绝 {flow['deny']} 次: {flow['src_ip']}:{flow['src_port']} -> {flow['dst_ip']}:{flow['dst_port']} ({flow['protocol']})",
                "src_ip": flow["src_ip"],
                "dst_ip": flow["dst_ip"],
                "dst_port": flow["dst_port"],
                "deny_count": flow["deny"],
            })

    # 排序五元组流：按总命中数倒序
    sorted_flows = sorted(five_tuple_flows.values(), key=lambda x: x["total"], reverse=True)
    top_flows = sorted_flows[:limit]

    return {
        "project_id": project_id,
        "total_flows": len(events),
        "permit_count": permit_count,
        "deny_count": deny_count,
        "total_up_bytes": total_up_bytes,
        "total_down_bytes": total_down_bytes,
        "top_source_ips": [{"ip": k, "count": v} for k, v in _top_n(source_ips, limit)],
        "top_target_ips": [{"ip": k, "count": v} for k, v in _top_n(target_ips, limit)],
        "top_target_ports": [{"port": k, "count": v} for k, v in _top_n(target_ports, limit)],
        "protocols": [{"protocol": k, "count": v} for k, v in _top_n(protocols, limit)],
        "top_flows": top_flows,
        "behaviors": behaviors,
        "timeline": timeline,
    }


@router.get("/projects/{project_id}/logs/operations")
async def get_logs_operations(
    project_id: int,
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    # 查询项目所有 material 的 LogEvent
    mat_stmt = select(Material.id).where(Material.project_id == project_id)
    mat_res = await db.execute(mat_stmt)
    material_ids = [row[0] for row in mat_res.all()] or [-1]

    # 仅统计操作相关事件
    stmt = (
        select(LogEvent)
        .where(LogEvent.material_id.in_(material_ids))
        .where(LogEvent.event_type.in_(_OPERATION_EVENT_TYPES))
        .order_by(LogEvent.timestamp.asc().nullslast(), LogEvent.id.asc())
    )
    res = await db.execute(stmt)
    events = list(res.scalars().all())

    by_type: Dict[str, int] = {}
    users: Dict[str, int] = {}
    devices: Dict[str, int] = {}
    command_timeline: List[Dict[str, Any]] = []
    auth_events: List[Dict[str, Any]] = []

    for ev in events:
        et = ev.event_type or "other"
        by_type[et] = by_type.get(et, 0) + 1
        if ev.user:
            users[ev.user] = users.get(ev.user, 0) + 1
        if ev.device:
            devices[ev.device] = devices.get(ev.device, 0) + 1

        if et == "command":
            command_timeline.append({
                "time": ev.timestamp.isoformat() if ev.timestamp else None,
                "user": ev.user or "",
                "command": ev.command or "",
                "result": ev.result or "",
            })
        elif et == "auth":
            auth_events.append({
                "time": ev.timestamp.isoformat() if ev.timestamp else None,
                "user": ev.user or "",
                "source_ip": ev.source_ip or "",
                "result": ev.result or "",
            })

    # 限制返回数量
    command_timeline = command_timeline[:limit]
    auth_events = auth_events[:limit]

    return {
        "project_id": project_id,
        "total_operations": len(events),
        "by_type": [{"type": k, "count": v} for k, v in _top_n(by_type, len(by_type))],
        "top_users": [{"user": k, "count": v} for k, v in _top_n(users, limit)],
        "top_devices": [{"device": k, "count": v} for k, v in _top_n(devices, limit)],
        "command_timeline": command_timeline,
        "auth_events": auth_events,
    }


# 失败登录的结果关键字
_FAILED_RESULT_KEYWORDS = ("fail", "failed", "denied", "error", "incorrect")


@router.get("/projects/{project_id}/logs/behavior")
async def get_logs_behavior(
    project_id: int,
    session_gap_minutes: int = Query(30, ge=1, le=1440),
    db: AsyncSession = Depends(get_db),
):
    # 查询项目所有 material 的 LogEvent
    mat_stmt = select(Material.id).where(Material.project_id == project_id)
    mat_res = await db.execute(mat_stmt)
    material_ids = [row[0] for row in mat_res.all()] or [-1]

    stmt = (
        select(LogEvent)
        .where(LogEvent.material_id.in_(material_ids))
        .order_by(LogEvent.timestamp.asc().nullslast(), LogEvent.id.asc())
    )
    res = await db.execute(stmt)
    events = list(res.scalars().all())

    # 按 user 分组
    by_user: Dict[str, List[LogEvent]] = {}
    for ev in events:
        u = ev.user or "unknown"
        by_user.setdefault(u, []).append(ev)

    users_summary: List[Dict[str, Any]] = []
    anomalies: List[Dict[str, Any]] = []
    session_timeline: List[Dict[str, Any]] = []
    total_sessions = 0
    session_gap = timedelta(minutes=session_gap_minutes)

    for user, user_events in by_user.items():
        # 排除时间戳为空的事件用于计算 first_seen/last_seen
        ts_events = [e for e in user_events if e.timestamp]
        first_seen = min((e.timestamp for e in ts_events), default=None)
        last_seen = max((e.timestamp for e in ts_events), default=None)
        source_ips = sorted({e.source_ip for e in user_events if e.source_ip})
        devices = sorted({e.device for e in user_events if e.device})

        users_summary.append({
            "user": user,
            "action_count": len(user_events),
            "first_seen": first_seen.isoformat() if first_seen else None,
            "last_seen": last_seen.isoformat() if last_seen else None,
            "source_ips": source_ips,
            "devices": devices,
        })

        # 异常检测1：非工作时间操作（22:00-06:00）
        for ev in ts_events:
            hour = ev.timestamp.hour
            if hour >= 22 or hour < 6:
                anomalies.append({
                    "type": "off_hours",
                    "description": f"非工作时间操作: {ev.event_type or 'unknown'}",
                    "time": ev.timestamp.isoformat(),
                    "user": user,
                })

        # 异常检测2：多次失败登录（>=3 次）
        failed_auth = [
            e for e in user_events
            if (e.event_type or "").lower() == "auth"
            and (e.result or "").lower() in _FAILED_RESULT_KEYWORDS
        ]
        if len(failed_auth) >= 3:
            anomalies.append({
                "type": "multiple_failed_auth",
                "description": f"多次失败登录: {len(failed_auth)} 次",
                "time": failed_auth[-1].timestamp.isoformat() if failed_auth[-1].timestamp else None,
                "user": user,
            })

        # 异常检测3：使用多个源 IP（>3 视为可疑）
        if len(source_ips) > 3:
            anomalies.append({
                "type": "multiple_source_ips",
                "description": f"使用多个源IP: {len(source_ips)} 个",
                "time": last_seen.isoformat() if last_seen else None,
                "user": user,
            })

        # 划分会话：按时间间隔 session_gap
        if ts_events:
            ts_events_sorted = sorted(ts_events, key=lambda e: e.timestamp)
            user_session_idx = 0
            current_session = [ts_events_sorted[0]]
            for ev in ts_events_sorted[1:]:
                if ev.timestamp - current_session[-1].timestamp > session_gap:
                    # 关闭当前会话
                    user_session_idx += 1
                    total_sessions += 1
                    session_timeline.append({
                        "session_id": f"{user}-{user_session_idx}",
                        "user": user,
                        "start": current_session[0].timestamp.isoformat(),
                        "end": current_session[-1].timestamp.isoformat(),
                        "event_count": len(current_session),
                        "actions": sorted({(e.event_type or "unknown") for e in current_session}),
                    })
                    current_session = [ev]
                else:
                    current_session.append(ev)
            # 处理最后一个会话
            user_session_idx += 1
            total_sessions += 1
            session_timeline.append({
                "session_id": f"{user}-{user_session_idx}",
                "user": user,
                "start": current_session[0].timestamp.isoformat(),
                "end": current_session[-1].timestamp.isoformat(),
                "event_count": len(current_session),
                "actions": sorted({(e.event_type or "unknown") for e in current_session}),
            })

    # 异常按时间倒序排序（无时间的排在最后）
    anomalies.sort(key=lambda x: x.get("time") or "", reverse=True)

    return {
        "project_id": project_id,
        "total_sessions": total_sessions,
        "users": users_summary,
        "anomalies": anomalies,
        "session_timeline": session_timeline,
    }
