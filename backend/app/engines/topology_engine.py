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
        edge_keys: set = set()

        for ev in events:
            et = str(ev.get("event_type", "")).lower()
            src = ev.get("source_ip")
            dev = ev.get("device") or ev.get("target_ip")

            # 兼容 ssh_session parser 输出的 "connection" 事件类型
            if et in ("ssh", "connect", "connection", "login", "auth") and src and dev:
                dev_key = f"dev-{dev}"
                if dev_key not in nodes:
                    nid = self._gen_id()
                    nodes[dev_key] = {
                        "id": nid,
                        "node_type": "switch",
                        "name": str(dev),
                        "ip_address": dev if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", str(dev)) else None,
                        "interface_desc": "被管理设备（SSH/登录会话目标）",
                        "source_material": "log:device",
                    }
                host_key = f"host-{src}"
                if host_key not in nodes:
                    hid = self._gen_id()
                    nodes[host_key] = {
                        "id": hid,
                        "node_type": self._make_host_type(),
                        "name": f"管理主机-{src}",
                        "ip_address": src,
                        "interface_desc": "运维/管理终端（SSH客户端源）",
                        "source_material": "log:ssh-source",
                    }
                ek = (nodes[host_key]["id"], nodes[dev_key]["id"], "ssh_session")
                if ek not in edge_keys:
                    edge_keys.add(ek)
                    edges.append({
                        "id": self._gen_id(),
                        "source_node": nodes[host_key]["id"],
                        "target_node": nodes[dev_key]["id"],
                        "edge_type": "ssh_session",
                        "bandwidth": None,
                        "source_material": f"log:{ev.get('line_no', '?')}",
                    })

        return {"nodes": list(nodes.values()), "edges": edges}

    @staticmethod
    def _ip_to_subnet(ip: str, prefix: int = 24) -> str:
        """将 IP 归并到 /24 网段，用于节点聚合。"""
        m = re.match(r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$", str(ip))
        if not m:
            return str(ip)
        if prefix == 24:
            return f"{m.group(1)}.{m.group(2)}.{m.group(3)}.0/24"
        return str(ip)

    def extract_from_csv_traffic(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """从 CSV 流量日志提取拓扑：按 /24 网段聚合主机，生成防火墙为中心的流量边。"""
        nodes: Dict[str, Dict[str, Any]] = {}
        edges: List[Dict[str, Any]] = []
        edge_flow_count: Dict[tuple, int] = {}

        fw_id = self._gen_id()
        fw_name = "防火墙(流量汇聚点)"
        nodes[fw_name] = {
            "id": fw_id,
            "node_type": "firewall",
            "name": fw_name,
            "ip_address": None,
            "interface_desc": "所有流量经过的安全网关，上联网络出口、下联内网交换机",
            "source_material": "traffic:synthesized",
        }

        src_subnets: Dict[str, Dict[str, Any]] = {}
        dst_subnets: Dict[str, Dict[str, Any]] = {}

        for ev in events:
            dst = ev.get("target_ip") or ev.get("dst")
            src = ev.get("source_ip") or ev.get("src")
            bytes_val = ev.get("_bytes") or ev.get("bytes") or 0
            try:
                bytes_val = int(bytes_val)
            except (ValueError, TypeError):
                bytes_val = 0

            if dst:
                subnet = self._ip_to_subnet(dst)
                if subnet not in dst_subnets:
                    did = self._gen_id()
                    dst_subnets[subnet] = {
                        "id": did,
                        "ip_count": 0,
                        "bytes": 0,
                    }
                    nodes[f"dst-{subnet}"] = {
                        "id": did,
                        "node_type": "host",
                        "name": f"服务器群 {subnet}",
                        "ip_address": subnet,
                        "interface_desc": "下联服务器网段（防火墙保护的内网区域）",
                        "source_material": "traffic:dst-aggregated",
                    }
                dst_subnets[subnet]["ip_count"] += 1
                dst_subnets[subnet]["bytes"] += bytes_val
                ek = (fw_id, nodes[f"dst-{subnet}"]["id"], "traffic_flow")
                edge_flow_count[ek] = edge_flow_count.get(ek, 0) + 1

            if src:
                subnet = self._ip_to_subnet(src)
                if subnet not in src_subnets:
                    sid = self._gen_id()
                    src_subnets[subnet] = {
                        "id": sid,
                        "ip_count": 0,
                        "bytes": 0,
                    }
                    nodes[f"src-{subnet}"] = {
                        "id": sid,
                        "node_type": "host",
                        "name": f"客户端网段 {subnet}",
                        "ip_address": subnet,
                        "interface_desc": "上联防火墙的客户端/访客网段",
                        "source_material": "traffic:src-aggregated",
                    }
                src_subnets[subnet]["ip_count"] += 1
                src_subnets[subnet]["bytes"] += bytes_val
                ek2 = (nodes[f"src-{subnet}"]["id"], fw_id, "traffic_flow")
                edge_flow_count[ek2] = edge_flow_count.get(ek2, 0) + 1

        for (src_id, dst_id, etype), count in edge_flow_count.items():
            edges.append({
                "id": self._gen_id(),
                "source_node": src_id,
                "target_node": dst_id,
                "edge_type": etype,
                "bandwidth": f"{count} flows",
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

    def compute_node_descriptions(self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """分析边图，为每个节点生成上下行/流量走势说明。

        根据节点的连接关系（入边=上游/上联，出边=下游/下联）和邻居类型，
        生成如"上联防火墙，下联接入交换机，旁挂上网行为管理"的描述。
        """
        # 构建 id -> node 映射
        node_map: Dict[Any, Dict[str, Any]] = {}
        for n in nodes:
            node_map[n.get("id")] = n

        # 构建邻接关系：upstream（入边源）、downstream（出边目标）
        upstream: Dict[Any, List[Any]] = {}
        downstream: Dict[Any, List[Any]] = {}
        for e in edges:
            src = e.get("source_node")
            tgt = e.get("target_node")
            downstream.setdefault(src, []).append(tgt)
            upstream.setdefault(tgt, []).append(src)

        # 节点类型中文标签
        type_label = {
            "firewall": "防火墙",
            "router": "路由器",
            "switch": "交换机",
            "host": "主机/终端",
        }

        def short_name(nid: Any) -> str:
            n = node_map.get(nid)
            if not n:
                return str(nid)
            name = n.get("name") or ""
            # 去掉常见前缀让描述更简洁
            name = re.sub(r"^(管理主机|客户端网段|服务器群|NextHop|VPN)\s*-?\s*", "", name)
            ip = n.get("ip_address") or ""
            # 如果名字像 IP 段，用网段表示
            if re.match(r"^\d+\.\d+\.\d+\.0/\d+$", str(name)):
                return f"网段 {name}"
            if ip and re.match(r"^\d+\.\d+\.\d+\.0/\d+$", str(ip)):
                return f"网段 {ip}"
            return name or (f"IP {ip}" if ip else f"节点{nid}")

        def node_type_of(nid: Any) -> str:
            n = node_map.get(nid)
            return (n.get("node_type") or "").lower() if n else ""

        result = []
        for n in nodes:
            nid = n.get("id")
            nt = (n.get("node_type") or "").lower()
            name = (n.get("name") or "").lower()

            up_ids = list(dict.fromkeys(upstream.get(nid, [])))  # 去重保序
            down_ids = list(dict.fromkeys(downstream.get(nid, [])))

            # 分类邻居：按类型分组
            up_firewalls = [i for i in up_ids if node_type_of(i) == "firewall"]
            up_switches = [i for i in up_ids if node_type_of(i) == "switch"]
            up_routers = [i for i in up_ids if node_type_of(i) == "router"]
            up_hosts = [i for i in up_ids if node_type_of(i) == "host"]

            down_firewalls = [i for i in down_ids if node_type_of(i) == "firewall"]
            down_switches = [i for i in down_ids if node_type_of(i) == "switch"]
            down_routers = [i for i in down_ids if node_type_of(i) == "router"]
            down_hosts = [i for i in down_ids if node_type_of(i) == "host"]

            parts: List[str] = []

            # 根据节点类型生成上下联描述
            if nt == "firewall":
                # 防火墙：上联通常是出口路由器/上游交换机，下联是核心交换机/内网
                up_labels = [short_name(i) for i in up_routers + up_switches if i in node_map]
                down_labels = [short_name(i) for i in down_switches + down_hosts if i in node_map]
                side_labels = [short_name(i) for i in up_hosts if i in node_map]  # 旁挂：来自主机的管理流量
                if up_labels:
                    parts.append(f"上联{ '、'.join(up_labels[:2]) }")
                if down_labels:
                    parts.append(f"下联{ '、'.join(down_labels[:2]) }")
                if side_labels:
                    parts.append(f"旁挂{ '、'.join(side_labels[:1]) }（管理接入）")
                if not parts:
                    parts.append("安全网关（流量过滤与访问控制）")

            elif nt == "router":
                up_labels = [short_name(i) for i in up_switches + up_routers if i in node_map]
                down_labels = [short_name(i) for i in down_switches + down_hosts if i in node_map]
                if up_labels:
                    parts.append(f"上联{ '、'.join(up_labels[:2]) }")
                if down_labels:
                    parts.append(f"下联{ '、'.join(down_labels[:2]) }")
                if not parts:
                    parts.append("路由节点（网间转发）")

            elif nt == "switch":
                is_core = "core" in name or "backbone" in name or "核心" in name
                if is_core:
                    # 核心交换机：上联防火墙/路由器，下联接入交换机，旁挂上网行为管理
                    up_labels = [short_name(i) for i in up_firewalls + up_routers if i in node_map]
                    down_labels = [short_name(i) for i in down_switches + down_hosts if i in node_map]
                    side_labels = [short_name(i) for i in up_hosts + down_hosts if i in node_map]
                    if up_labels:
                        parts.append(f"上联{ '、'.join(up_labels[:2]) }")
                    if down_labels:
                        parts.append(f"下联{ '、'.join(down_labels[:2]) }")
                    # 旁挂检测：如果有主机直连，可能是旁挂设备（如上网行为管理）
                    host_neighbors = [short_name(i) for i in up_hosts + down_hosts if i in node_map]
                    if host_neighbors and not down_switches:
                        parts.append(f"旁挂{ '、'.join(host_neighbors[:1]) }")
                    if not parts:
                        parts.append("核心交换机（骨干转发，二/三层交换）")
                else:
                    # 接入交换机：上联核心交换机，下联服务器/终端
                    up_labels = [short_name(i) for i in up_switches + up_firewalls + up_routers if i in node_map]
                    down_labels = [short_name(i) for i in down_hosts + down_switches if i in node_map]
                    if up_labels:
                        parts.append(f"上联{ '、'.join(up_labels[:2]) }")
                    if down_labels:
                        parts.append(f"下联{ '、'.join(down_labels[:2]) }")
                    if not parts:
                        parts.append("接入交换机（终端接入，二层交换）")

            elif nt == "host":
                up_labels = [short_name(i) for i in up_switches + up_firewalls + up_routers if i in node_map]
                if up_labels:
                    parts.append(f"接入{ '、'.join(up_labels[:1]) }")
                else:
                    parts.append("终端节点")
                # 如果是服务器群/网段聚合节点
                if "网段" in (n.get("name") or "") or "/24" in (n.get("ip_address") or ""):
                    parts.append("（该网段内多台主机流量聚合）")

            else:
                if up_ids:
                    parts.append(f"上联{ '、'.join(short_name(i) for i in up_ids[:2] if i in node_map) }")
                if down_ids:
                    parts.append(f"下联{ '、'.join(short_name(i) for i in down_ids[:2] if i in node_map) }")
                if not parts:
                    parts.append("网络节点")

            # 补充流量统计
            total_edges = len(up_ids) + len(down_ids)
            if total_edges > 0:
                parts.append(f"（共{total_edges}条连接）")

            out = dict(n)
            desc = "，".join(parts)
            # 保留已有描述中的补充信息
            existing_desc = n.get("interface_desc") or ""
            if existing_desc and existing_desc not in desc:
                desc = f"{desc}；原始: {existing_desc}"
            out["interface_desc"] = desc
            result.append(out)

        return result
