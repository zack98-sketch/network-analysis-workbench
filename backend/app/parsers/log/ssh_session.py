import re
from datetime import datetime
from typing import List, Dict, Any
from .base import ILogParser


IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
TIMESTAMP_RE = re.compile(
    r"(\d{4}[-/]\d{2}[-/]\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?|\d{2}:\d{2}:\d{2})"
)
CONNECT_RE = re.compile(r"\[BEGIN\]\s*(.+?)\s*Connecting to\s+([\d\.]+)[: ]")
# Xshell 导出格式：[1: 2024-01-15 09:30:45] 或 [2024-01-15 09:30:45] 或行首时间戳
XSHELL_TS_RE = re.compile(r"\[(?:\d+:\s*)?(\d{4}[-/]\d{2}[-/]\d{2}\s+\d{2}:\d{2}:\d{2})\]")
XSHELL_CONNECT_RE = re.compile(r"Connecting to\s+([\d\.]+)(?::(\d+))?", re.IGNORECASE)
XSHELL_HOST_HEADER_RE = re.compile(r"Host\s*:\s*([\d\.]+)", re.IGNORECASE)
PASSWORD_PROMPT_RE = re.compile(r"password:", re.IGNORECASE)
PUBLICKEY_RE = re.compile(r"(publickey|key-based|Publickey)", re.IGNORECASE)
PROMPT_RE = re.compile(r"^([<\[][^\]>]+[>\]])\s*(.*)$")
# 兼容 Xshell 命令行：行首有时间戳后跟提示符，如 "[09:30:45] <host> display version"
XSHELL_PROMPT_RE = re.compile(r"^(?:\[[^\]]*\]\s*)?([<\[][^\]>]+[>\]])\s*(.*)$")
DISCONNECT_RE = re.compile(r"(Connection closed|Disconnected|Closed connection|logout|quit|exit)", re.IGNORECASE)
LOGIN_SUCCESS_RE = re.compile(r"(Login\s+success|Logged\s+in|Authentication\s+success|Welcome)", re.IGNORECASE)
LOGIN_FAIL_RE = re.compile(r"(Login\s+fail|Authentication\s+fail|Access\s+denied|Permission\s+denied|Password\s+incorrect)", re.IGNORECASE)


class SSHSessionParser(ILogParser):
    def can_parse(self, file_path: str, header_bytes: bytes, sample_lines: List[str]) -> bool:
        header_text = header_bytes.decode("utf-8", errors="replace")
        joined = " ".join(sample_lines[:20])

        # 原有 [BEGIN]/Connecting to 格式
        if "[BEGIN]" in header_text or "Connecting to" in header_text:
            return True

        # Xshell 导出格式特征
        xshell_markers = [
            "Xshell" in header_text,
            bool(XSHELL_CONNECT_RE.search(joined)),
            bool(XSHELL_HOST_HEADER_RE.search(header_text)),
            bool(XSHELL_TS_RE.search(joined)),
        ]
        if sum(xshell_markers) >= 1:
            return True

        # 通用 SSH 会话特征：提示符 + 命令
        if re.search(r"[<\[][\w\-\.]+[>\]]\s*(display|system-view|quit|save|interface)", joined, re.IGNORECASE):
            return True

        if "[BEGIN]" in joined and "Connecting to" in joined:
            return True

        return False

    def _extract_timestamp(self, line: str, stripped: str) -> str:
        """优先识别 Xshell 时间戳格式，回退到通用时间戳。"""
        m = XSHELL_TS_RE.search(line)
        if m:
            return m.group(1)
        m2 = TIMESTAMP_RE.search(line)
        if m2:
            ts = m2.group(1)
            if len(ts) <= 8:
                today = datetime.now().strftime("%Y-%m-%d")
                ts = f"{today} {ts}"
            return ts
        return None

    def parse(self, file_path: str) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        current_event = None
        current_device = None
        current_source_ip = None
        current_user = None
        line_no = 0
        connect_emitted = False

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            for raw_line in f:
                line_no += 1
                line = raw_line.rstrip("\n")
                stripped = line.strip()

                if not stripped:
                    continue

                timestamp = self._extract_timestamp(line, stripped)
                ip_matches = IPV4_RE.findall(line)

                # Xshell Host 头部识别
                host_header = XSHELL_HOST_HEADER_RE.search(stripped)
                if host_header and current_device is None:
                    current_device = host_header.group(1)
                    continue

                # 连接事件（兼容 [BEGIN] 与 Xshell "Connecting to"）
                connect_match = CONNECT_RE.search(line) or XSHELL_CONNECT_RE.search(stripped)
                if connect_match and not connect_emitted:
                    if timestamp is None:
                        ts2 = TIMESTAMP_RE.search(line)
                        if ts2:
                            timestamp = ts2.group(1)
                            if len(timestamp) <= 8:
                                today = datetime.now().strftime("%Y-%m-%d")
                                timestamp = f"{today} {timestamp}"
                    if isinstance(connect_match.re, type(CONNECT_RE)):
                        current_device = connect_match.group(2)
                    else:
                        current_device = connect_match.group(1)
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
                    connect_emitted = True
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

                if LOGIN_SUCCESS_RE.search(stripped):
                    current_event = {
                        "timestamp": timestamp,
                        "event_type": "auth",
                        "source_ip": current_source_ip,
                        "target_ip": current_device,
                        "user": current_user,
                        "device": current_device,
                        "command": None,
                        "result": "success",
                        "detail": "登录成功",
                        "raw_line": stripped,
                        "line_no": line_no,
                    }
                    events.append(current_event)
                    continue

                if LOGIN_FAIL_RE.search(stripped):
                    current_event = {
                        "timestamp": timestamp,
                        "event_type": "auth",
                        "source_ip": current_source_ip,
                        "target_ip": current_device,
                        "user": current_user,
                        "device": current_device,
                        "command": None,
                        "result": "failed",
                        "detail": "登录失败",
                        "raw_line": stripped,
                        "line_no": line_no,
                    }
                    events.append(current_event)
                    continue

                # 命令行：兼容 Xshell 时间戳前缀 + VRP/H3C 提示符
                prompt_match = XSHELL_PROMPT_RE.match(stripped)
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
