import re
import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import defaultdict
from datetime import datetime, timedelta

from app.config import settings


class RiskEngine:
    def __init__(self):
        self.rules_dir = settings.BASE_DIR / "app" / "rules"
        self.config_rules = self._load_rules("config_security.yaml")
        self.log_rules = self._load_rules("log_audit.yaml")
        self.traffic_rules = self._load_rules("traffic_anomaly.yaml")
        self._risk_counter = 0

    def _load_rules(self, filename: str) -> List[Dict[str, Any]]:
        path = self.rules_dir / filename
        if not path.exists():
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                return data if isinstance(data, list) else []
        except Exception:
            return []

    def _next_risk_code(self) -> str:
        self._risk_counter += 1
        return f"RISK-{self._risk_counter:03d}"

    def _match_condition(self, item: Dict[str, Any], condition: Dict[str, Any]) -> bool:
        key_pat = condition.get("key", "") or condition.get("field", "")
        op = condition.get("op") or "eq"
        expected = condition.get("value")

        item_key = str(item.get("key", "") or "")
        item_value = str(item.get("value", "") or item.get("raw_line", "") or "")

        if op == "missing":
            combined = f"{item_key} {item_value}"
            return not re.search(key_pat, combined, re.IGNORECASE)

        if not re.search(key_pat, item_key, re.IGNORECASE):
            return False

        actual_value = item_value if item_value else item_key

        if op in (None, "eq"):
            if expected is None:
                return True
            return str(expected).lower() in actual_value.lower()

        if op == "contains":
            return str(expected).lower() in actual_value.lower()

        if op == "regex_contains":
            return bool(re.search(str(expected), actual_value, re.IGNORECASE))

        if op == "regex_not_contains":
            return not bool(re.search(str(expected), actual_value, re.IGNORECASE))

        if op == "missing_in_section":
            return True

        if op == "in_list":
            if isinstance(expected, list):
                return actual_value.lower() in [str(x).lower() for x in expected]
            return False

        if op == "not_in_cidr":
            return True

        if op == "hour_range":
            return True

        if op == "gt":
            try:
                return float(actual_value) > float(expected)
            except (ValueError, TypeError):
                return False

        return False

    def analyze_config(self, config_tree: Dict[str, Any]) -> List[Dict[str, Any]]:
        findings = []
        sections = config_tree.get("sections", []) if isinstance(config_tree, dict) else []
        emitted_rule_names: set = set()

        # Build a GLOBAL combined string for whole-config "missing" checks
        global_all_keys = " ".join(
            str(it.get("key", "")) for s in sections for it in s.get("items", [])
        )
        global_all_values = " ".join(
            str(it.get("value", "")) for s in sections for it in s.get("items", [])
        )
        global_all_raws = " ".join(
            str(it.get("raw_line", "")) for s in sections for it in s.get("items", [])
        )
        combined_global = f"{global_all_keys} {global_all_values} {global_all_raws}"

        for rule in self.config_rules:
            rule_name = rule.get("name", rule.get("description", ""))
            trigger = rule.get("trigger", {})
            section_type = trigger.get("section_type")
            conditions = trigger.get("conditions", [])

            has_section_level_op = any(
                (c.get("op") or "eq") in ("missing", "missing_in_section")
                for c in conditions
            )

            filtered_sections = [
                s for s in sections
                if s.get("section_type") == section_type
            ]

            # For pure global "missing"-style rules without any matching section of the declared type,
            # also try a GLOBAL pass across all sections (info-center may live in section_type="log"
            # while rule declares section_type="system").
            global_fallback_applicable = (
                has_section_level_op and not filtered_sections
            ) or (
                has_section_level_op and section_type == "system"
            )

            sections_to_check = list(filtered_sections)
            if global_fallback_applicable:
                # Synthesize a pseudo-section that contains ALL items, used for the global pass
                all_items = [it for s in sections for it in s.get("items", [])]
                pseudo = {
                    "section_type": "__global__",
                    "section_name": "__global__",
                    "items": all_items,
                }
                if pseudo not in sections_to_check:
                    sections_to_check.append(pseudo)

            for section in sections_to_check:
                items = section.get("items", [])
                matched_all = True
                matched_items = []

                # Pre-combine ALL raw_lines & key-value pairs for SECTION-LEVEL ops
                all_keys = " ".join(str(it.get("key", "")) for it in items)
                all_values = " ".join(str(it.get("value", "")) for it in items)
                all_raw_lines = " ".join(str(it.get("raw_line", "")) for it in items)
                combined_section = f"{all_keys} {all_values} {all_raw_lines}"

                for condition in conditions:
                    op = condition.get("op") or "eq"
                    key_pat = condition.get("key", "") or condition.get("field", "")

                    if op in ("missing", "missing_in_section"):
                        # Use GLOBAL combined view for these ops (more accurate for missing config)
                        effective_combined = combined_global if combined_global else combined_section
                        present_in_section = bool(re.search(key_pat, effective_combined, re.IGNORECASE))
                        cond_matched = (not present_in_section)
                        if cond_matched:
                            matched_items.append(items[0] if items else {"line_no": "?"})
                    elif op == "regex_contains":
                        expected = str(condition.get("value", ""))
                        cond_matched = False
                        for item in items:
                            iv = f"{item.get('key','')} {item.get('value','')} {item.get('raw_line','')}"
                            # Match key_pat against the FULL item string, not just item.key
                            if re.search(key_pat, iv, re.IGNORECASE) and re.search(expected, iv, re.IGNORECASE):
                                cond_matched = True
                                matched_items.append(item)
                                break
                    elif op == "regex_not_contains":
                        expected = str(condition.get("value", ""))
                        key_hit = any(re.search(key_pat, f"{it.get('key','')} {it.get('value','')} {it.get('raw_line','')}", re.IGNORECASE) for it in items)
                        if not key_hit:
                            cond_matched = False
                        else:
                            has_bad = False
                            anchor_item = None
                            for item in items:
                                iv_full = f"{item.get('key','')} {item.get('value','')} {item.get('raw_line','')}"
                                if re.search(key_pat, iv_full, re.IGNORECASE):
                                    anchor_item = item
                                    if re.search(expected, iv_full, re.IGNORECASE):
                                        has_bad = True
                                        break
                            cond_matched = (not has_bad)
                            if cond_matched and anchor_item:
                                matched_items.append(anchor_item)
                    else:
                        cond_matched = False
                        for item in items:
                            if self._match_condition(item, condition):
                                cond_matched = True
                                matched_items.append(item)
                                break

                    if not cond_matched:
                        matched_all = False
                        break

                if matched_all:
                    # Dedup by rule_name: emit each rule at most once per config tree
                    dedup_key = rule_name
                    if dedup_key in emitted_rule_names:
                        continue
                    emitted_rule_names.add(dedup_key)

                    src_item = matched_items[0] if matched_items else {"line_no": "?"}
                    findings.append({
                        "risk_code": self._next_risk_code(),
                        "severity": rule.get("severity", "medium"),
                        "category": rule.get("rule_type", "config"),
                        "description": rule.get("description", ""),
                        "source_ref": f"{config_tree.get('device_name', 'config')}:{src_item.get('line_no', '?')}",
                        "remediation_cmd": rule.get("remediation_cmd", rule.get("remediation", "")),
                        "standard_ref": rule.get("standard_ref", ""),
                        "status": "pending",
                    })

        return findings

    def analyze_logs(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        findings = []

        for ev in events:
            et = str(ev.get("event_type", "")).lower()
            ts = ev.get("timestamp")
            if et in ("auth", "login") and ts:
                try:
                    if isinstance(ts, str):
                        ts_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    else:
                        ts_dt = ts
                    hour = ts_dt.hour
                    if hour >= 22 or hour < 6:
                        findings.append({
                            "risk_code": self._next_risk_code(),
                            "severity": "medium",
                            "category": "log_audit",
                            "description": f"非工作时间登录行为: 用户{ev.get('user', '?')} 从 {ev.get('source_ip', '?')} 在 {ts_dt.strftime('%Y-%m-%d %H:%M')} 登录",
                            "source_ref": f"log:{ev.get('line_no', '?')}",
                            "remediation_cmd": "1. 联系账户持有人确认是否本人操作；2. 若异常重置密码并强制下线；3. 配置AAA时间段策略限制登录时段。",
                            "standard_ref": "等保2.0三级 8.1.4.3",
                            "status": "pending",
                        })
                except Exception:
                    pass

        fail_windows: Dict[tuple, List[datetime]] = defaultdict(list)
        for ev in events:
            et = str(ev.get("event_type", "")).lower()
            result = str(ev.get("result", "")).lower()
            if et in ("auth", "login", "deny") and any(k in result for k in ("fail", "deny", "invalid")):
                key = (ev.get("source_ip"), ev.get("user"))
                ts = ev.get("timestamp")
                try:
                    if isinstance(ts, str):
                        ts_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    else:
                        ts_dt = ts
                    fail_windows[key].append(ts_dt)
                except Exception:
                    pass

        for (src_ip, user), timestamps in fail_windows.items():
            timestamps.sort()
            for i in range(len(timestamps)):
                window_end = timestamps[i] + timedelta(minutes=5)
                count = sum(1 for t in timestamps[i:] if t <= window_end)
                if count > 5:
                    findings.append({
                        "risk_code": self._next_risk_code(),
                        "severity": "high",
                        "category": "log_audit",
                        "description": f"5分钟内登录失败次数超限: 用户{user} 源IP {src_ip} 失败{count}次，疑似暴力破解",
                        "source_ref": f"log:aggregated",
                        "remediation_cmd": "1. 在防火墙/ACL临时封禁源IP；2. 锁定账户并通知管理员；3. 配置登录失败锁定策略 local-user policy password retry-interval 5 retry-time 3 block-time 30",
                        "standard_ref": "等保2.0三级 8.1.2.2 / 8.1.3.2",
                        "status": "pending",
                    })
                    break

        user_sources: Dict[str, Dict[str, List[datetime]]] = defaultdict(lambda: defaultdict(list))
        for ev in events:
            et = str(ev.get("event_type", "")).lower()
            result = str(ev.get("result", "")).lower()
            user = ev.get("user")
            src_ip = ev.get("source_ip")
            if et in ("auth", "login") and any(k in result for k in ("success", "accept", "allowed")) and user and src_ip:
                ts = ev.get("timestamp")
                try:
                    if isinstance(ts, str):
                        ts_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    else:
                        ts_dt = ts
                    user_sources[user][src_ip].append(ts_dt)
                except Exception:
                    pass

        for user, sources in user_sources.items():
            all_timestamps = []
            for src, tsl in sources.items():
                all_timestamps.extend(tsl)
            all_timestamps.sort()
            for i in range(len(all_timestamps)):
                window_end = all_timestamps[i] + timedelta(minutes=10)
                ips_in_window = set()
                for src, tsl in sources.items():
                    if any(t >= all_timestamps[i] and t <= window_end for t in tsl):
                        ips_in_window.add(src)
                if len(ips_in_window) > 3:
                    findings.append({
                        "risk_code": self._next_risk_code(),
                        "severity": "medium",
                        "category": "log_audit",
                        "description": f"同一账户多源IP并发登录: 用户{user} 10分钟内从 {len(ips_in_window)} 个不同IP登录，疑似凭据泄露",
                        "source_ref": f"log:aggregated",
                        "remediation_cmd": "1. 确认是否合法多人共用；2. 开启单点登录互斥策略 local-user policy single-login；3. 重置账户密码并启用MFA。",
                        "standard_ref": "等保2.0三级 8.1.2.2",
                        "status": "pending",
                    })
                    break

        return findings

    def analyze_traffic(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        findings = []

        minute_buckets: Dict[tuple, int] = defaultdict(int)
        for ev in events:
            et = str(ev.get("event_type", "")).lower()
            src_ip = ev.get("source_ip")
            if et in ("traffic", "permit", "deny") and src_ip:
                ts = ev.get("timestamp")
                try:
                    if isinstance(ts, str):
                        ts_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    else:
                        ts_dt = ts if isinstance(ts, datetime) else datetime.now()
                    bucket_key = (src_ip, ts_dt.strftime("%Y-%m-%d %H:%M"))
                    minute_buckets[bucket_key] += 1
                except Exception:
                    pass

        for (src_ip, bucket), count in minute_buckets.items():
            if count > 10000:
                findings.append({
                    "risk_code": self._next_risk_code(),
                    "severity": "medium",
                    "category": "traffic_anomaly",
                    "description": f"单源IP每分钟命中数异常: {src_ip} 在 {bucket} 触发 {count} 条策略命中，疑似端口扫描或DoS攻击",
                    "source_ref": f"traffic:aggregated",
                    "remediation_cmd": "1. 检查源IP是否属于合法监控系统；2. 启用IP会话限速；3. 临时下发黑洞路由或ACL封禁异常源IP。",
                    "standard_ref": "等保2.0三级 8.1.3.3",
                    "status": "pending",
                })

        for ev in events:
            detail = ev.get("detail_json") or {}
            if not isinstance(detail, dict):
                detail = {}
            protocol = str(ev.get("_protocol") or detail.get("protocol") or "").lower()
            dst_port = ev.get("destination_port") or detail.get("destination_port")
            if "tcp" in protocol and dst_port == 23:
                findings.append({
                    "risk_code": self._next_risk_code(),
                    "severity": "high",
                    "category": "traffic_anomaly",
                    "description": f"出站访问Telnet端口23: {ev.get('source_ip', '?')} -> {ev.get('target_ip', '?')}:23，疑似被控主机外联或恶意登录",
                    "source_ref": f"traffic:{ev.get('line_no', '?')}",
                    "remediation_cmd": "1. 阻断Telnet会话；2. 溯源查杀内网主机恶意进程；3. 边界添加出站拒绝TCP/23规则并启用威胁情报联动。",
                    "standard_ref": "等保2.0三级 8.1.3.3 / 8.1.4.2",
                    "status": "pending",
                })

        icmp_pps: Dict[tuple, int] = defaultdict(int)
        for ev in events:
            detail = ev.get("detail_json") or {}
            if not isinstance(detail, dict):
                detail = {}
            protocol = str(ev.get("_protocol") or detail.get("protocol") or "").lower()
            src_ip = ev.get("source_ip")
            dst_ip = ev.get("target_ip")
            if "icmp" in protocol and src_ip and dst_ip:
                key = (src_ip, dst_ip)
                icmp_pps[key] += 1

        for (src, dst), count in icmp_pps.items():
            if count > 100:
                findings.append({
                    "risk_code": self._next_risk_code(),
                    "severity": "low",
                    "category": "traffic_anomaly",
                    "description": f"ICMP洪水异常: {src} -> {dst} ICMP速率>100pps (累计{count})，疑似Ping Flood或探测扫描",
                    "source_ref": "traffic:aggregated",
                    "remediation_cmd": "1. 检查是否为健康检查；2. 配置接口 icmp rate-limit 100；3. 启用 anti-attack icmp-flood。",
                    "standard_ref": "等保2.0三级 8.1.3.3 / 8.1.4.2",
                    "status": "pending",
                })

        return findings

    def analyze_all(self, project_ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
        self._risk_counter = 0
        all_findings = []

        config_trees = project_ctx.get("config_trees") or []
        for ct in config_trees:
            all_findings.extend(self.analyze_config(ct))

        log_events = project_ctx.get("log_events") or []
        all_findings.extend(self.analyze_logs(log_events))

        traffic_events = project_ctx.get("traffic_events") or log_events
        all_findings.extend(self.analyze_traffic(traffic_events))

        return all_findings
