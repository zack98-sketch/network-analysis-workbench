import re
import uuid
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, timedelta
from collections import defaultdict


class CorrelationEngine:
    def __init__(self):
        self._session_id_counter = 0

    def _next_session_id(self) -> str:
        self._session_id_counter += 1
        return f"sess-{self._session_id_counter:05d}"

    def _parse_ts(self, ts: Any) -> Optional[datetime]:
        if ts is None:
            return None
        if isinstance(ts, datetime):
            return ts
        try:
            return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        except Exception:
            return None

    def build_sessions(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        grouped: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = defaultdict(list)

        for ev in events:
            src = str(ev.get("source_ip") or "")
            tgt = str(ev.get("target_ip") or ev.get("device") or "")
            user = str(ev.get("user") or "")
            if not src and not tgt and not user:
                continue
            key = (src, tgt, user)
            grouped[key].append(ev)

        sessions: List[Dict[str, Any]] = []
        gap_threshold = timedelta(minutes=30)

        for key, evs in grouped.items():
            evs_sorted = sorted(evs, key=lambda e: self._parse_ts(e.get("timestamp")) or datetime.min)
            current_session_evs: List[Dict[str, Any]] = []
            last_ts = None

            for ev in evs_sorted:
                ts = self._parse_ts(ev.get("timestamp"))
                if ts is None:
                    current_session_evs.append(ev)
                    continue
                if last_ts is None:
                    current_session_evs = [ev]
                    last_ts = ts
                elif ts - last_ts <= gap_threshold:
                    current_session_evs.append(ev)
                    last_ts = ts
                else:
                    if current_session_evs:
                        sessions.append(self._make_session(key, current_session_evs))
                    current_session_evs = [ev]
                    last_ts = ts

            if current_session_evs:
                sessions.append(self._make_session(key, current_session_evs))

        return sessions

    def _make_session(self, key: Tuple[str, str, str], events: List[Dict[str, Any]]) -> Dict[str, Any]:
        timestamps = [self._parse_ts(e.get("timestamp")) for e in events if self._parse_ts(e.get("timestamp"))]
        start = min(timestamps) if timestamps else None
        end = max(timestamps) if timestamps else None

        results = [str(e.get("result", "")).lower() for e in events]
        status = "active"
        if any(r in ("fail", "deny", "invalid") for r in results):
            status = "failed" if not any(r in ("success", "accept", "allowed") for r in results) else "mixed"
        elif any(r in ("success", "accept", "allowed") for r in results):
            status = "success"
        if any(str(e.get("event_type", "")).lower() in ("logout", "disconnect") for e in events):
            status = "closed" if status == "success" else status

        src, tgt, user = key
        return {
            "id": self._next_session_id(),
            "source_ip": src,
            "target_ip": tgt,
            "user": user,
            "start_time": start.isoformat() if start else None,
            "end_time": end.isoformat() if end else None,
            "events": events,
            "event_count": len(events),
            "status": status,
        }

    def build_behavior_graph(self, events: List[Dict[str, Any]], sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []
        node_set = set()
        edge_set = set()

        def add_node(nid: str, ntype: str, label: str):
            if nid not in node_set:
                node_set.add(nid)
                nodes.append({"id": nid, "type": ntype, "label": label})

        def add_edge(src: str, tgt: str, etype: str, value: int = 1, meta: Optional[Dict] = None):
            key = (src, tgt, etype)
            if key in edge_set:
                for e in edges:
                    if e["source"] == src and e["target"] == tgt and e["type"] == etype:
                        e["value"] = e.get("value", 0) + value
                        return
            edge_set.add(key)
            edges.append({
                "source": src,
                "target": tgt,
                "type": etype,
                "value": value,
                "meta": meta or {},
            })

        for ev in events:
            user = ev.get("user")
            src = ev.get("source_ip")
            tgt = ev.get("target_ip") or ev.get("device")
            cmd = ev.get("command")
            et = ev.get("event_type")

            if user:
                add_node(f"user:{user}", "user", user)
            if src:
                add_node(f"ip:{src}", "ip", src)
            if tgt:
                add_node(f"device:{tgt}", "device", str(tgt))
            if cmd:
                cmd_key = f"cmd:{hash(cmd) % 100000:05d}"
                add_node(cmd_key, "command", (cmd[:40] + "...") if len(cmd) > 40 else cmd)

            if user and src:
                add_edge(f"user:{user}", f"ip:{src}", "uses_ip", 1, {"event_type": et})
            if user and tgt:
                add_edge(f"user:{user}", f"device:{tgt}", "accesses_device", 1, {"event_type": et})
            if src and tgt:
                add_edge(f"ip:{src}", f"device:{tgt}", "connects_to", 1, {"event_type": et})
            if user and cmd:
                cmd_key = f"cmd:{hash(cmd) % 100000:05d}"
                add_edge(f"user:{user}", cmd_key, "executed_command", 1, {"event_type": et})

        for sess in sessions:
            sid = sess.get("id")
            add_node(f"session:{sid}", "session", sid)
            user = sess.get("user")
            src = sess.get("source_ip")
            tgt = sess.get("target_ip")
            if user:
                add_edge(f"user:{user}", f"session:{sid}", "has_session", sess.get("event_count", 1))
            if src:
                add_edge(f"ip:{src}", f"session:{sid}", "session_from", sess.get("event_count", 1))
            if tgt:
                add_edge(f"session:{sid}", f"device:{tgt}", "session_to", sess.get("event_count", 1))

        return {"nodes": nodes, "edges": edges}

    def find_cross_file_links(
        self,
        materials: List[Dict[str, Any]],
        events: List[Dict[str, Any]],
        config_tree: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        links: List[Dict[str, Any]] = []

        config_sysnames = set()
        config_ips = set()

        sections = config_tree.get("sections", []) if isinstance(config_tree, dict) else []
        dev_name = config_tree.get("device_name")
        if dev_name:
            config_sysnames.add(str(dev_name))

        for section in sections:
            items = section.get("items", [])
            for item in items:
                combined = f"{item.get('key', '')} {item.get('value', '')} {item.get('raw_line', '')}"
                sys_match = re.search(r"sysname\s+(\S+)", combined, re.IGNORECASE)
                if sys_match:
                    config_sysnames.add(sys_match.group(1).strip())
                host_match = re.search(r"hostname\s+(\S+)", combined, re.IGNORECASE)
                if host_match:
                    config_sysnames.add(host_match.group(1).strip())
                for ip in re.findall(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b", combined):
                    try:
                        parts = [int(p) for p in ip.split(".")]
                        if all(0 <= p <= 255 for p in parts):
                            config_ips.add(ip)
                    except ValueError:
                        pass

        for ev in events:
            ev_dev = str(ev.get("device") or "")
            ev_tgt = str(ev.get("target_ip") or "")

            for sn in config_sysnames:
                if sn and (sn.lower() == ev_dev.lower() or sn.lower() in ev_dev.lower()):
                    links.append({
                        "type": "hostname_match",
                        "config_entity": sn,
                        "log_entity": ev_dev,
                        "material_ref": ev.get("line_no"),
                        "description": f"配置sysname/hostname '{sn}' 与日志设备字段 '{ev_dev}' 匹配",
                    })

            if ev_tgt and ev_tgt in config_ips:
                links.append({
                    "type": "ip_interface_match",
                    "config_entity": ev_tgt,
                    "log_entity": ev_tgt,
                    "material_ref": ev.get("line_no"),
                    "description": f"日志目标IP {ev_tgt} 匹配配置中的接口IP地址",
                })

        seen = set()
        deduped = []
        for l in links:
            k = (l["type"], l["config_entity"], l["log_entity"])
            if k in seen:
                continue
            seen.add(k)
            deduped.append(l)
        return deduped
