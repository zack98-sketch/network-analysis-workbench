import traceback
from typing import Any, Dict, List, Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.parsers.router import FileRouter
from app.engines.risk_engine import RiskEngine
from app.engines.topology_engine import TopologyEngine

from app.models.material import Material, ParseStatus
from app.models.log_event import LogEvent
from app.models.config_item import ConfigItem
from app.models.doc_index import DocIndex
from app.models.risk_finding import RiskFinding, Severity, RiskStatus
from app.models.topology import TopoNode, TopoEdge


class ParseService:
    def __init__(self):
        self.router = FileRouter()
        self.risk_engine = RiskEngine()
        self.topo_engine = TopologyEngine()

    async def parse_material(self, material_id: int, db: AsyncSession) -> Material:
        stmt = select(Material).where(Material.id == material_id)
        result = await db.execute(stmt)
        material = result.scalar_one_or_none()
        if material is None:
            raise ValueError(f"Material {material_id} not found")

        material.parse_status = ParseStatus.PARSING
        await db.flush()

        try:
            parser = self.router.route(material.file_path)
            if parser is None:
                raise RuntimeError(f"No parser matched for {material.file_path}")

            parse_result = parser.parse(material.file_path)

            category, parser_name, _conf = self.router.detect_type(material.file_path)
            material.parser_type = f"{category}/{parser_name}"

            if category == "log" and isinstance(parse_result, list):
                await self._save_log_events(material.project_id, material.id, parse_result, db)
                if parse_result and parse_result[0].get("device"):
                    material.device_name = str(parse_result[0]["device"])

            elif category == "config":
                if isinstance(parse_result, dict):
                    tree = parse_result
                else:
                    tree = {"sections": [], "device_name": None}
                await self._save_config_items(material.project_id, material.id, tree, db)
                if tree.get("device_name"):
                    material.device_name = tree["device_name"]

            elif category == "doc" and isinstance(parse_result, list):
                await self._save_doc_index(material.project_id, material.id, parse_result, db)

            material.file_type = category
            material.parse_status = ParseStatus.SUCCESS

            await db.flush()
            await db.refresh(material)

            project_ctx = await self._gather_project_context(material.project_id, db)
            project_ctx.setdefault("traffic_events", [])

            findings = self.risk_engine.analyze_all(project_ctx)
            await self._save_risk_findings(material.project_id, material.id, findings, db)

            existing_topo = await self._get_project_topology(material.project_id, db)
            new_extract = {"nodes": [], "edges": []}

            if category == "config" and isinstance(parse_result, dict):
                new_extract = self.topo_engine.extract_from_config(parse_result)
            elif category == "log":
                if material.parser_type and "structured_csv" in material.parser_type:
                    new_extract = self.topo_engine.extract_from_csv_traffic(parse_result)
                else:
                    new_extract = self.topo_engine.extract_from_logs(parse_result)

            merged = self.topo_engine.merge_topology(existing_topo, new_extract)
            merged["nodes"] = self.topo_engine.assign_default_positions(merged["nodes"])
            # 根据边图分析上下行/流量走势，生成节点说明
            merged["nodes"] = self.topo_engine.compute_node_descriptions(merged["nodes"], merged["edges"])
            await self._save_project_topology(material.project_id, merged, db)

            await db.commit()
            await db.refresh(material)
            return material

        except Exception as exc:
            await db.rollback()
            stmt2 = select(Material).where(Material.id == material_id)
            r2 = await db.execute(stmt2)
            material = r2.scalar_one_or_none()
            if material is not None:
                material.parse_status = ParseStatus.FAILED
                await db.commit()
            raise exc

    async def _save_log_events(self, project_id: int, material_id: int, events: List[Dict[str, Any]], db: AsyncSession) -> None:
        await db.execute(delete(LogEvent).where(LogEvent.material_id == material_id))
        from datetime import datetime as _dt
        objs: List[LogEvent] = []
        for idx, ev in enumerate(events):
            detail = ev.get("detail_json")
            detail_text = ev.get("detail")
            if detail is None and detail_text:
                detail = {"value": detail_text}
            elif not isinstance(detail, dict):
                detail = None
            if isinstance(detail, dict):
                for k in ("_protocol", "_src_port", "_dst_port", "_bytes"):
                    if k in ev and k not in detail:
                        detail[k.lstrip("_")] = ev[k]
            ts = ev.get("timestamp")
            if isinstance(ts, str) and ts:
                try:
                    ts = _dt.fromisoformat(ts.replace("Z", "+00:00"))
                except Exception:
                    ts = None
            objs.append(LogEvent(
                project_id=project_id,
                material_id=material_id,
                timestamp=ts,
                event_type=ev.get("event_type"),
                source_ip=ev.get("source_ip"),
                target_ip=ev.get("target_ip"),
                destination_port=ev.get("_dst_port") or ev.get("destination_port"),
                _protocol=ev.get("_protocol") or ev.get("protocol"),
                _bytes=ev.get("_bytes") or ev.get("bytes"),
                user=ev.get("user"),
                device=ev.get("device"),
                command=ev.get("command"),
                result=ev.get("result"),
                detail_json=detail,
                raw_line=ev.get("raw_line"),
                line_no=ev.get("line_no") if ev.get("line_no") is not None else (idx + 1),
            ))
        # 批量 add + 单次 flush，避免逐行写库长事务持锁导致 database is locked
        db.add_all(objs)
        await db.flush()

    async def _save_config_items(self, project_id: int, material_id: int, tree: Dict[str, Any], db: AsyncSession) -> None:
        await db.execute(delete(ConfigItem).where(ConfigItem.material_id == material_id))
        device_name = tree.get("device_name")
        sections = tree.get("sections", []) if isinstance(tree, dict) else []
        objs: List[ConfigItem] = []
        for section in sections:
            stype = section.get("section_type")
            sname = section.get("section_name")
            items = section.get("items", [])
            for item in items:
                objs.append(ConfigItem(
                    project_id=project_id,
                    material_id=material_id,
                    device_name=device_name,
                    section_type=stype,
                    section_name=sname,
                    line_no=item.get("line_no"),
                    raw_line=item.get("raw_line"),
                    key=item.get("key"),
                    value=item.get("value"),
                    indent_level=item.get("indent_level") or 0,
                    annotation=item.get("annotation"),
                    doc_ref=item.get("doc_ref"),
                    is_risk=bool(item.get("is_risk")),
                    risk_level=item.get("risk_level") or "none",
                ))
        db.add_all(objs)
        await db.flush()

    async def _save_doc_index(self, project_id: int, material_id: int, entries: List[Dict[str, Any]], db: AsyncSession) -> None:
        await db.execute(delete(DocIndex).where(DocIndex.material_id == material_id))
        objs: List[DocIndex] = []
        for entry in entries:
            objs.append(DocIndex(
                project_id=project_id,
                material_id=material_id,
                title=entry.get("title"),
                section_path=entry.get("section_path"),
                content_text=entry.get("content_text"),
                config_keywords=entry.get("config_keywords"),
                page_no=entry.get("page_no"),
            ))
        db.add_all(objs)
        await db.flush()

    async def _gather_project_context(self, project_id: int, db: AsyncSession) -> Dict[str, Any]:
        mat_stmt = select(Material.id, Material.project_id).where(Material.project_id == project_id)
        mat_res = await db.execute(mat_stmt)
        material_ids = [row[0] for row in mat_res.all()]

        log_events: List[Dict[str, Any]] = []
        config_trees: List[Dict[str, Any]] = []

        # 单次查询所有 material 的 LogEvent（按 material_id 分组），消除 N+1
        if material_ids:
            log_stmt = (
                select(LogEvent)
                .where(LogEvent.material_id.in_(material_ids))
                .order_by(LogEvent.material_id, LogEvent.id)
            )
            log_res = await db.execute(log_stmt)
            log_by_mid: Dict[int, List[Any]] = {}
            for le in log_res.scalars().all():
                log_by_mid.setdefault(le.material_id, []).append(le)
            for mid in material_ids:
                for le in log_by_mid.get(mid, []):
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

            # 单次查询所有 material 的 ConfigItem（按 material_id 分组），消除 N+1
            ci_stmt = (
                select(ConfigItem)
                .where(ConfigItem.material_id.in_(material_ids))
                .order_by(ConfigItem.material_id, ConfigItem.id)
            )
            ci_res = await db.execute(ci_stmt)
            ci_by_mid: Dict[int, List[Any]] = {}
            for ci in ci_res.scalars().all():
                ci_by_mid.setdefault(ci.material_id, []).append(ci)
            for mid in material_ids:
                cis = ci_by_mid.get(mid, [])
                if not cis:
                    continue
                sections_dict: Dict[tuple, List[Any]] = {}
                device_name = None
                for ci in cis:
                    if device_name is None:
                        device_name = ci.device_name
                    key = (ci.section_type or "", ci.section_name or "")
                    sections_dict.setdefault(key, []).append({
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
                for (st, sn), items in sections_dict.items():
                    sections.append({"section_type": st, "section_name": sn, "items": items})
                config_trees.append({
                    "material_id": mid,
                    "device_name": device_name,
                    "sections": sections,
                })

        return {
            "project_id": project_id,
            "material_ids": material_ids,
            "log_events": log_events,
            "config_trees": config_trees,
            "traffic_events": log_events,
        }

    async def _save_risk_findings(
        self,
        project_id: int,
        material_id: int,
        findings: List[Dict[str, Any]],
        db: AsyncSession,
    ) -> None:
        await db.execute(delete(RiskFinding).where(
            RiskFinding.project_id == project_id,
            RiskFinding.material_id == material_id,
        ))
        sev_map = {
            "high": Severity.HIGH,
            "critical": Severity.CRITICAL,
            "medium": Severity.MEDIUM,
            "low": Severity.LOW,
            "info": Severity.LOW,
        }
        objs: List[RiskFinding] = []
        for f in findings:
            sev = sev_map.get((f.get("severity") or "").lower(), Severity.MEDIUM)
            objs.append(RiskFinding(
                project_id=project_id,
                material_id=material_id,
                risk_code=f.get("risk_code", "RISK-000"),
                severity=sev,
                category=f.get("category"),
                description=f.get("description"),
                source_ref=f.get("source_ref"),
                remediation_cmd=f.get("remediation_cmd"),
                standard_ref=f.get("standard_ref"),
                status=RiskStatus.OPEN,
            ))
        db.add_all(objs)
        await db.flush()

    async def _get_project_topology(self, project_id: int, db: AsyncSession) -> Dict[str, Any]:
        n_stmt = select(TopoNode).where(TopoNode.project_id == project_id)
        n_res = await db.execute(n_stmt)
        nodes = []
        for n in n_res.scalars().all():
            nodes.append({
                "id": n.id,
                "node_type": n.node_type,
                "name": n.name,
                "ip_address": n.ip_address,
                "interface_desc": n.interface_desc,
                "pos_x": n.pos_x or 0.0,
                "pos_y": n.pos_y or 0.0,
                "source_material": n.source_material,
            })

        e_stmt = select(TopoEdge).where(TopoEdge.project_id == project_id)
        e_res = await db.execute(e_stmt)
        edges = []
        for e in e_res.scalars().all():
            edges.append({
                "id": e.id,
                "source_node": e.source_node,
                "target_node": e.target_node,
                "edge_type": e.edge_type,
                "bandwidth": e.bandwidth,
                "source_material": e.source_material,
            })
        return {"nodes": nodes, "edges": edges}

    async def _save_project_topology(self, project_id: int, topo: Dict[str, Any], db: AsyncSession) -> None:
        await db.execute(delete(TopoEdge).where(TopoEdge.project_id == project_id))
        await db.execute(delete(TopoNode).where(TopoNode.project_id == project_id))

        # 批量插入节点：一次性 add_all + 单次 flush，再统一 refresh 拿自增 id
        # 这是之前 database is locked 的根因（逐行 flush+refresh 长事务持锁）
        id_rewrite: Dict[Any, int] = {}
        node_objs: List[TopoNode] = []
        node_keys: List[Any] = []
        for n in topo.get("nodes", []):
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
            node_objs.append(new_node)
            node_keys.append(n.get("id"))

        if node_objs:
            db.add_all(node_objs)
            await db.flush()  # 单次 flush，所有节点一次性拿到 id
            for key, obj in zip(node_keys, node_objs):
                id_rewrite[key] = obj.id

        edge_objs: List[TopoEdge] = []
        for e in topo.get("edges", []):
            old_src = e.get("source_node")
            old_tgt = e.get("target_node")
            new_src = id_rewrite.get(old_src, old_src)
            new_tgt = id_rewrite.get(old_tgt, old_tgt)
            if new_src is None or new_tgt is None:
                continue
            try:
                edge_objs.append(TopoEdge(
                    project_id=project_id,
                    source_node=int(new_src),
                    target_node=int(new_tgt),
                    edge_type=e.get("edge_type"),
                    bandwidth=e.get("bandwidth"),
                    source_material=e.get("source_material"),
                ))
            except (TypeError, ValueError):
                continue
        if edge_objs:
            db.add_all(edge_objs)
            await db.flush()
