import re
from datetime import datetime
from typing import List, Dict, Any
from .base import ILogParser


IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
TIMESTAMP_RE = re.compile(
    r"(\d{4}[-/]\d{2}[-/]\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?|\d{2}:\d{2}:\d{2})"
)
CONNECT_RE = re.compile(r"\[BEGIN\]\s*(.+?)\s*Connecting to\s+([\d\.]+)[: ]")
PASSWORD_PROMPT_RE = re.compile(r"password:", re.IGNORECASE)
PUBLICKEY_RE = re.compile(r"(publickey|key-based|Publickey)", re.IGNORECASE)
PROMPT_RE = re.compile(r"^([<\[][^\]>]+[>\]])\s*(.*)$")
DISCONNECT_RE = re.compile(r"(Connection closed|Disconnected|Closed connection|logout|quit|exit)", re.IGNORECASE)


class SSHSessionParser(ILogParser):
    def can_parse(self, file_path: str, header_bytes: bytes, sample_lines: List[str]) -> bool:
        header_text = header_bytes.decode("utf-8", errors="replace")
        if "[BEGIN]" not in header_text and "Connecting to" not in header_text:
            joined = " ".join(sample_lines[:10])
            if "[BEGIN]" not in joined or "Connecting to" not in joined:
                return False
        return True

    def parse(self, file_path: str) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        current_event = None
        current_device = None
        current_source_ip = None
        current_user = None
        line_no = 0

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            for raw_line in f:
                line_no += 1
                line = raw_line.rstrip("\n")
                stripped = line.strip()

                if not stripped:
                    continue

                ts_match = TIMESTAMP_RE.search(line)
                timestamp = ts_match.group(1) if ts_match else None
                if timestamp and len(timestamp) <= 8:
                    try:
                        today = datetime.now().strftime("%Y-%m-%d")
                        timestamp = f"{today} {timestamp}"
                    except Exception:
                        pass

                ip_matches = IPV4_RE.findall(line)

                connect_match = CONNECT_RE.search(line)
                if connect_match:
                    if timestamp is None and connect_match.group(1):
                        ts2 = TIMESTAMP_RE.search(connect_match.group(1))
                        if ts2:
                            timestamp = ts2.group(1)
                    current_source_ip = None
                    for ip in ip_matches:
                        current_device = ip
                        break
                    current_event = {
                        "timestamp": timestamp,
                        "event_type": "connection",
                        "source_ip": current_source_ip,
                        "target_ip": current_device,
                        "user": current_user,
                        "device": current_device,
                        "command": None,
                        "result": "start",
                        "detail": f"SSH会话开始连接 {current_device}",
                        "raw_line": stripped,
                        "line_no": line_no,
                    }
                    events.append(current_event)
                    continue

                if PASSWORD_PROMPT_RE.search(stripped):
                    current_event = {
                        "timestamp": timestamp,
                        "event_type": "auth",
                        "source_ip": current_source_ip,
                        "target_ip": current_device,
                        "user": current_user,
                        "device": current_device,
                        "command": None,
                        "result": "password_prompt",
                        "detail": "密码认证提示",
                        "raw_line": stripped,
                        "line_no": line_no,
                    }
                    events.append(current_event)
                    continue

                if PUBLICKEY_RE.search(stripped):
                    current_event = {
                        "timestamp": timestamp,
                        "event_type": "auth",
                        "source_ip": current_source_ip,
                        "target_ip": current_device,
                        "user": current_user,
                        "device": current_device,
                        "command": None,
                        "result": "publickey",
                        "detail": "公钥认证",
                        "raw_line": stripped,
                        "line_no": line_no,
                    }
                    events.append(current_event)
                    continue

                prompt_match = PROMPT_RE.match(stripped)
                if prompt_match:
                    prompt_part = prompt_match.group(1)
                    cmd_part = prompt_match.group(2).strip()
                    host_match = re.search(r"[<\[]([^\]>]+)[>\]]", prompt_part)
                    if host_match:
                        device_name = host_match.group(1)
                        if device_name and device_name != current_device:
                            current_device = device_name
                    if cmd_part:
                        src_ip = ip_matches[0] if ip_matches else current_source_ip
                        current_event = {
                            "timestamp": timestamp,
                            "event_type": "command",
                            "source_ip": src_ip,
                            "target_ip": current_device if not IPV4_RE.fullmatch(current_device or "") else current_device,
                            "user": current_user,
                            "device": current_device,
                            "command": cmd_part,
                            "result": "executed",
                            "detail": f"执行命令: {cmd_part}",
                            "raw_line": stripped,
                            "line_no": line_no,
                        }
                        events.append(current_event)
                    continue

                if DISCONNECT_RE.search(stripped):
                    current_event = {
                        "timestamp": timestamp,
                        "event_type": "disconnect",
                        "source_ip": current_source_ip,
                        "target_ip": current_device,
                        "user": current_user,
                        "device": current_device,
                        "command": None,
                        "result": "closed",
                        "detail": "SSH会话断开",
                        "raw_line": stripped,
                        "line_no": line_no,
                    }
                    events.append(current_event)
                    continue

                if current_event and not current_event.get("detail"):
                    current_event["detail"] = (current_event.get("detail") or "") + stripped
                else:
                    events.append({
                        "timestamp": timestamp,
                        "event_type": "output",
                        "source_ip": current_source_ip,
                        "target_ip": current_device,
                        "user": current_user,
                        "device": current_device,
                        "command": None,
                        "result": None,
                        "detail": stripped,
                        "raw_line": stripped,
                        "line_no": line_no,
                    })

        return events
