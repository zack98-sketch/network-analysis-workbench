import re
import ipaddress
from typing import List, Dict, Any, Tuple, Optional


class TopologyEngine:
    def __init__(self):
        self._next_id = 1

    def _gen_id(self) -> int:
        nid = self._next_id
        self._next_id += 1
        return nid

    def _infer_node_type(self, vendor: str, device_type: str) -> str:
        v = (vendor or "").lower()
        dt = (device_type or "").lower()
        if "usg" in dt or "firewall" in dt or "fw" in dt or "secospace" in v:
            return "firewall"
        if "s" in dt and "switch" in dt:
            return "switch"
        if "ce" in dt or "router" in dt or "ne" in dt or "ar" in dt:
            return "router"
        if "huawei" in v or "h3c" in v:
            if any(x in dt for x in ("fw", "usg")):
                return "firewall"
            return "switch"
        return "switch"

    def _make_host_type(self) -> str:
        return "host"

    def extract_from_config(self, config_tree: Dict[str, Any]) -> Dict[str, Any]:
        nodes: Dict[str, Dict[str, Any]] = {}
        edges: List[Dict[str, Any]] = []

        device_name = config_tree.get("device_name") or "UnknownDevice"
        vendor = config_tree.get("vendor", "")

        device_type = self._infer_node_type(vendor, device_name)
        dev_node_id = self._gen_id()
        nodes[device_name] = {
            "id": dev_node_id,
            "node_type": device_type,
            "name": device_name,
            "ip_address": None,
            "interface_desc": None,
            "source_material": "config",
        }

        device_ips = []

        sections = config_tree.get("sections", []) if isinstance(config_tree, dict) else []
        for section in sections:
            st = section.get("section_type", "")
            sn = section.get("section_name", "")
            items = section.get("items", [])

            if st == "interface":
                iface_name = sn or ""
                iface_desc = None
                iface_ip = None

                for item in items:
                    key = str(item.get("key", "") or "")
                    val = str(item.get("value", "") or item.get("raw_line", "") or "")
                    combined = f"{key} {val}"

                    desc_match = re.search(r"description\s+(.*)", combined, re.IGNORECASE)
                    if desc_match:
                        iface_desc = desc_match.group(1).strip().strip('"').strip("'")

                    ip_match = re.search(r"ip\s+address\s+(\d{1,3}(?:\.\d{1,3}){3})\s+(\d{1,3}(?:\.\d{1,3}){3}|/\d{1,2})", combined, re.IGNORECASE)
                    if ip_match:
                        iface_ip = ip_match.group(1)
                        device_ips.append(iface_ip)

                if iface_desc:
                    to_match = re.search(r"to-([A-Za-z0-9_\-\.]+)", iface_desc, re.IGNORECASE)
                    if to_match:
                        peer_name = to_match.group(1)
                        if peer_name not in nodes:
                            pid = self._gen_id()
                            nodes[peer_name] = {
                                "id": pid,
                                "node_type": "switch",
                                "name": peer_name,
                                "ip_address": None,
                                "interface_desc": iface_desc,
                                "source_material": "config",
                            }
                        edges.append({
                            "id": self._gen_id(),
                            "source_node": dev_node_id,
                            "target_node": nodes[peer_name]["id"],
                            "edge_type": "physical",
                            "bandwidth": None,
                            "source_material": f"config:{iface_name}",
                        })

            if st == "static_route" or st == "system":
                for item in items:
                    combined = f"{item.get('key', '')} {item.get('value', '')} {item.get('raw_line', '')}"
                    nh_match = re.search(r"next-hop\s+(\d{1,3}(?:\.\d{1,3}){3})", combined, re.IGNORECASE)
                    if nh_match:
                        nh = nh_match.group(1)
                        peer_key = f"nh-{nh}"
                        if peer_key not in nodes:
                            pid = self._gen_id()
                            nodes[peer_key] = {
                                "id": pid,
                                "node_type": "router",
                                "name": f"NextHop-{nh}",
                                "ip_address": nh,
                                "interface_desc": None,
                                "source_material": "config:route",
                            }
                        edges.append({
                            "id": self._gen_id(),
                            "source_node": dev_node_id,
                            "target_node": nodes[peer_key]["id"],
                            "edge_type": "route",
                            "bandwidth": None,
                            "source_material": "config:static-route",
                        })

            if st == "vpn_instance":
                for item in items:
                    combined = f"{item.get('key', '')} {item.get('value', '')} {item.get('raw_line', '')}"
                    vpn_match = re.search(r"vpn-instance\s+(\S+)", combined, re.IGNORECASE)
                    if vpn_match:
                        vpn_name = vpn_match.group(1)
                        vpn_key = f"vpn-{vpn_name}"
                        if vpn_key not in nodes:
                            pid = self._gen_id()
                            nodes[vpn_key] = {
                                "id": pid,
                                "node_type": "router",
                                "name": f"VPN-{vpn_name}",
                                "ip_address": None,
                                "interface_desc": f"VRF {vpn_name}",
                                "source_material": "config:vpn",
                            }
                        edges.append({
                            "id": self._gen_id(),
                            "source_node": dev_node_id,
                            "target_node": nodes[vpn_key]["id"],
                            "edge_type": "vrf",
                            "bandwidth": None,
                            "source_material": "config:vpn-instance",
                        })

        if device_ips and not nodes[device_name].get("ip_address"):
            non_host = None
            for ip in device_ips:
                try:
                    if not ipaddress.ip_address(ip).is_private:
                        non_host = ip
                        break
                except ValueError:
                    pass
            nodes[device_name]["ip_address"] = non_host or device_ips[0]

        return {"nodes": list(nodes.values()), "edges": edges}

    def extract_from_logs(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        nodes: Dict[str, Dict[str, Any]] = {}
        edges: List[Dict[str, Any]] = []

        for ev in events:
            et = str(ev.get("event_type", "")).lower()
            src = ev.get("source_ip")
            dev = ev.get("device") or ev.get("target_ip")

            if et in ("ssh", "connect", "login", "auth") and src and dev:
                dev_key = f"dev-{dev}"
                if dev_key not in nodes:
                    nid = self._gen_id()
                    nodes[dev_key] = {
                        "id": nid,
                        "node_type": "switch",
                        "name": str(dev),
                        "ip_address": dev if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", str(dev)) else None,
                        "interface_desc": None,
                        "source_material": "log:device",
                    }
                host_key = f"host-{src}"
                if host_key not in nodes:
                    hid = self._gen_id()
                    nodes[host_key] = {
                        "id": hid,
                        "node_type": self._make_host_type(),
                        "name": f"Host-{src}",
                        "ip_address": src,
                        "interface_desc": None,
                        "source_material": "log:ssh-source",
                    }
                edges.append({
                    "id": self._gen_id(),
                    "source_node": nodes[host_key]["id"],
                    "target_node": nodes[dev_key]["id"],
                    "edge_type": "ssh_session",
                    "bandwidth": None,
                    "source_material": f"log:{ev.get('line_no', '?')}",
                })

        return {"nodes": list(nodes.values()), "edges": edges}

    def extract_from_csv_traffic(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        nodes: Dict[str, Dict[str, Any]] = {}
        edges: List[Dict[str, Any]] = []

        fw_id = self._gen_id()
        fw_name = "Firewall-Core"
        nodes[fw_name] = {
            "id": fw_id,
            "node_type": "firewall",
            "name": fw_name,
            "ip_address": None,
            "interface_desc": "Traffic aggregation point",
            "source_material": "traffic:synthesized",
        }

        seen_dst = set()
        for ev in events:
            dst = ev.get("target_ip") or ev.get("dst")
            if not dst:
                continue
            if dst in seen_dst:
                continue
            seen_dst.add(dst)
            host_key = f"dst-{dst}"
            hid = self._gen_id()
            nodes[host_key] = {
                "id": hid,
                "node_type": self._make_host_type(),
                "name": f"Server-{dst}",
                "ip_address": dst,
                "interface_desc": None,
                "source_material": "traffic:dst",
            }
            edges.append({
                "id": self._gen_id(),
                "source_node": fw_id,
                "target_node": hid,
                "edge_type": "traffic_flow",
                "bandwidth": None,
                "source_material": "traffic:aggregated",
            })

            src = ev.get("source_ip") or ev.get("src")
            if src:
                src_key = f"src-{src}"
                if src_key not in nodes:
                    sid = self._gen_id()
                    nodes[src_key] = {
                        "id": sid,
                        "node_type": self._make_host_type(),
                        "name": f"Client-{src}",
                        "ip_address": src,
                        "interface_desc": None,
                        "source_material": "traffic:src",
                    }
                edges.append({
                    "id": self._gen_id(),
                    "source_node": nodes[src_key]["id"],
                    "target_node": fw_id,
                    "edge_type": "traffic_flow",
                    "bandwidth": None,
                    "source_material": "traffic:aggregated",
                })

        return {"nodes": list(nodes.values()), "edges": edges}

    def merge_topology(self, existing_topo: Dict[str, Any], new_extract: Dict[str, Any]) -> Dict[str, Any]:
        existing_nodes = existing_topo.get("nodes", []) if existing_topo else []
        existing_edges = existing_topo.get("edges", []) if existing_topo else []
        new_nodes = new_extract.get("nodes", []) if new_extract else []
        new_edges = new_extract.get("edges", []) if new_extract else []

        def node_key(n: Dict[str, Any]) -> Tuple[str, str]:
            return (str(n.get("name", "")), str(n.get("ip_address", "") or ""))

        seen = {}
        merged_nodes = []
        id_map = {}

        for n in existing_nodes:
            k = node_key(n)
            if k not in seen:
                seen[k] = n
                merged_nodes.append(n)
                id_map[n.get("id")] = n

        for n in new_nodes:
            k = node_key(n)
            if k in seen:
                existing = seen[k]
                for field in ("node_type", "interface_desc", "source_material"):
                    if not existing.get(field) and n.get(field):
                        existing[field] = n.get(field)
                if not existing.get("ip_address") and n.get("ip_address"):
                    existing["ip_address"] = n.get("ip_address")
                id_map[n.get("id")] = existing
            else:
                seen[k] = n
                merged_nodes.append(n)
                id_map[n.get("id")] = n

        for nlist in (existing_nodes, new_nodes):
            for n in nlist:
                old_id = n.get("id")
                if old_id not in id_map:
                    id_map[old_id] = n

        merged_edges = list(existing_edges)
        edge_keys = set((e.get("source_node"), e.get("target_node"), e.get("edge_type")) for e in existing_edges)
        for e in new_edges:
            src_old = e.get("source_node")
            tgt_old = e.get("target_node")
            src_new = id_map.get(src_old, {}).get("id", src_old)
            tgt_new = id_map.get(tgt_old, {}).get("id", tgt_old)
            key = (src_new, tgt_new, e.get("edge_type"))
            if key in edge_keys:
                continue
            edge_keys.add(key)
            merged_e = dict(e)
            merged_e["source_node"] = src_new
            merged_e["target_node"] = tgt_new
            merged_edges.append(merged_e)

        return {"nodes": merged_nodes, "edges": merged_edges}

    def assign_default_positions(self, nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        result = []

        layers = {
            "host_left": [],
            "firewall": [],
            "switch_top": [],
            "router": [],
            "switch_bottom": [],
            "host_right": [],
        }

        for n in nodes:
            nt = (n.get("node_type") or "").lower()
            name = (n.get("name") or "").lower()
            if nt == "firewall":
                layers["firewall"].append(n)
            elif nt == "router":
                layers["router"].append(n)
            elif nt == "switch":
                if "core" in name or "backbone" in name:
                    layers["switch_top"].append(n)
                else:
                    layers["switch_bottom"].append(n)
            elif nt == "host":
                ip = n.get("ip_address") or ""
                try:
                    if ip and ipaddress.ip_address(ip).is_private:
                        layers["host_left"].append(n)
                    else:
                        layers["host_right"].append(n)
                except ValueError:
                    if "client" in name or "src" in name:
                        layers["host_left"].append(n)
                    else:
                        layers["host_right"].append(n)
            else:
                layers["switch_bottom"].append(n)

        layer_positions = {
            "host_left": (15.0, 50.0, "vertical"),
            "switch_top": (50.0, 20.0, "horizontal"),
            "router": (35.0, 35.0, "horizontal"),
            "firewall": (50.0, 50.0, "center"),
            "switch_bottom": (65.0, 65.0, "horizontal"),
            "host_right": (85.0, 50.0, "vertical"),
        }

        for layer_name, layer_nodes in layers.items():
            if not layer_nodes:
                continue
            base_x, base_y, direction = layer_positions[layer_name]
            count = len(layer_nodes)
            for idx, node in enumerate(layer_nodes):
                if count == 1:
                    x, y = base_x, base_y
                elif direction == "horizontal":
                    spread = min(50.0, (count - 1) * 12.0)
                    start = base_x - spread / 2
                    x = start + idx * (spread / (count - 1)) if count > 1 else base_x
                    y = base_y
                elif direction == "vertical":
                    spread = min(60.0, (count - 1) * 10.0)
                    start = base_y - spread / 2
                    x = base_x
                    y = start + idx * (spread / (count - 1)) if count > 1 else base_y
                else:
                    x, y = base_x, base_y
                out = dict(node)
                out["pos_x"] = round(max(2.0, min(98.0, x)), 2)
                out["pos_y"] = round(max(2.0, min(98.0, y)), 2)
                result.append(out)

        return result
