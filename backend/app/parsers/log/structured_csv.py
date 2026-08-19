import re
import csv
from datetime import datetime
from typing import List, Dict, Any
from .base import ILogParser


IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
DATE_RE = re.compile(r"\d{4}[-/]\d{2}[-/]\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?")
KNOWN_COLS = {
    "time": "timestamp", "timestamp": "timestamp", "datetime": "timestamp", "date": "timestamp",
    "结束时间": "timestamp", "开始时间": "timestamp", "日志时间": "timestamp", "时间": "timestamp", "产生时间": "timestamp",
    "src": "source_ip", "source": "source_ip", "source_ip": "source_ip", "src_ip": "source_ip", "sip": "source_ip",
    "源地址": "source_ip", "源ip": "source_ip", "源ip地址": "source_ip", "nat源地址": "source_nat_ip",
    "dst": "target_ip", "dest": "target_ip", "target": "target_ip", "destination": "target_ip",
    "dest_ip": "target_ip", "dst_ip": "target_ip", "dip": "target_ip",
    "目的地址": "target_ip", "目的ip": "target_ip", "目的ip地址": "target_ip", "nat目的地址": "target_nat_ip",
    "destination_ip": "target_ip",
    "proto": "protocol", "protocol": "protocol",
    "协议": "protocol",
    "dst_port": "dst_port", "destination_port": "dst_port", "dest_port": "dst_port", "dport": "dst_port",
    "src_port": "src_port", "sport": "src_port", "source_port": "src_port",
    "action": "action", "result": "action", "verdict": "action",
    "动作": "action", "处理动作": "action", "会话关闭原因": "action",
    "bytes": "bytes", "byte": "bytes", "bytes_count": "bytes",
    "总流量(bytes)": "bytes", "总字节": "bytes", "字节数": "bytes",
    "上行流量(bytes)": "tx_bytes", "下行流量(bytes)": "rx_bytes",
    "时长(s)": "duration_sec",
    "user": "user", "username": "user",
    "用户": "user", "用户名": "user", "操作用户": "user",
    "cmd": "command", "command": "command",
    "命令": "command",
    "event": "event_type", "event_type": "event_type", "type": "event_type",
    "事件类型": "event_type", "类别": "event_type", "类型": "event_type",
    "host": "device", "device": "device", "hostname": "device",
    "设备": "device", "设备名": "device", "虚拟系统": "device",
    "源端口": "src_port", "目的端口": "dst_port", "nat源端口": "src_nat_port", "nat目的端口": "dst_nat_port",
    "安全策略": "security_policy", "带宽策略": "bandwidth_policy",
    "应用": "app", "应用大类": "app_category", "应用小类": "app_subcategory",
    "源安全区域": "src_zone", "目的安全区域": "dst_zone",
    "入接口": "in_interface", "出接口": "out_interface",
}


def _parse_datetime(val: str) -> str:
    if not val:
        return None
    val = val.strip()
    fmts = [
        "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d %H:%M:%S.%f", "%d/%m/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d",
    ]
    for fmt in fmts:
        try:
            return datetime.strptime(val, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            continue
    return val


class StructuredLogParser(ILogParser):
    def can_parse(self, file_path: str, header_bytes: bytes, sample_lines: List[str]) -> bool:
        if not sample_lines:
            return False
        first_line = sample_lines[0]
        try:
            reader = csv.reader([first_line])
            cols = next(reader)
        except Exception:
            return False
        if len(cols) < 3:
            return False
        matched = 0
        for c in cols:
            key = (c or "").strip()
            # check both Chinese original + lower English
            if key in KNOWN_COLS or key.lower() in KNOWN_COLS:
                matched += 1
        return matched >= 2

    def parse(self, file_path: str) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        line_no = 0

        with open(file_path, "r", encoding="utf-8", errors="replace", newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                return events
            col_map = {}
            for c in reader.fieldnames:
                key = (c or "").strip()
                if key in KNOWN_COLS:
                    col_map[KNOWN_COLS[key]] = c
                elif key.lower() in KNOWN_COLS:
                    col_map[KNOWN_COLS[key.lower()]] = c

            for row in reader:
                line_no += 1
                if not row:
                    continue

                ts_raw = row.get(col_map.get("timestamp", "")) if col_map.get("timestamp") else None
                timestamp = _parse_datetime(ts_raw) if ts_raw else None

                src = row.get(col_map.get("source_ip", "")) if col_map.get("source_ip") else None
                dst = row.get(col_map.get("target_ip", "")) if col_map.get("target_ip") else None
                if src:
                    s = str(src).strip()
                    if not IPV4_RE.match(s):
                        m = IPV4_RE.search(s)
                        src = m.group(0) if m else s
                    else:
                        src = s
                if dst:
                    d = str(dst).strip()
                    if not IPV4_RE.match(d):
                        m = IPV4_RE.search(d)
                        dst = m.group(0) if m else d
                    else:
                        dst = d

                action = row.get(col_map.get("action", "")) if col_map.get("action") else None
                protocol = (row.get(col_map.get("protocol", "")).strip() if col_map.get("protocol") else None)
                user = (row.get(col_map.get("user", "")).strip() if col_map.get("user") else None)
                command = (row.get(col_map.get("command", "")).strip() if col_map.get("command") else None)
                device = (row.get(col_map.get("device", "")).strip() if col_map.get("device") else None)
                event_type_raw = row.get(col_map.get("event_type", "")) if col_map.get("event_type") else None

                event_type = "traffic"
                if event_type_raw:
                    event_type = str(event_type_raw).lower()
                elif action:
                    a = str(action).lower()
                    if "deny" in a or "drop" in a or "reject" in a:
                        event_type = "deny"
                    elif "permit" in a or "allow" in a or "accept" in a:
                        event_type = "permit"
                    elif "login" in a or "auth" in a:
                        event_type = "login"

                detail_parts = []
                if protocol:
                    detail_parts.append(f"proto={protocol}")
                src_port = (row.get(col_map.get("src_port","")).strip() if col_map.get("src_port") else None)
                dst_port = (row.get(col_map.get("dst_port","")).strip() if col_map.get("dst_port") else None)
                if src_port: detail_parts.append(f"sport={src_port}")
                if dst_port: detail_parts.append(f"dport={dst_port}")
                for alias in ["src_zone","dst_zone","in_interface","out_interface",
                              "security_policy","bandwidth_policy","app","app_category","app_subcategory",
                              "tx_bytes","rx_bytes","duration_sec"]:
                    if col_map.get(alias):
                        val = (row.get(col_map[alias]) or "").strip()
                        if val:
                            detail_parts.append(f"{alias}={val}")
                bytes_val = row.get(col_map.get("bytes", "")) if col_map.get("bytes") else None
                if bytes_val:
                    detail_parts.append(f"bytes={bytes_val}")
                remaining = []
                used_keys = set(col_map.values())
                for k, v in row.items():
                    if k in used_keys or not v:
                        continue
                    remaining.append(f"{k}={v}")
                detail_parts.extend(remaining[:5])
                detail = "; ".join(detail_parts)

                raw_line = ",".join(f"{k}={v}" if " " in str(v) else str(v) for k, v in row.items())

                events.append({
                    "timestamp": timestamp,
                    "event_type": event_type,
                    "source_ip": src,
                    "target_ip": dst,
                    "user": user,
                    "device": device,
                    "command": command,
                    "result": action,
                    "detail": detail,
                    "raw_line": raw_line,
                    "line_no": line_no,
                    "_protocol": protocol,
                    "_src_port": src_port,
                    "_dst_port": dst_port,
                    "_bytes": bytes_val,
                })

        return events
