import re
from datetime import datetime
from typing import List, Dict, Any
from .base import ILogParser


IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
RFC3164_RE = re.compile(
    r"^<(?P<pri>\d{1,3})>(?P<mon>[A-Za-z]{3})\s+(?P<day>\d{1,2})\s+"
    r"(?P<time>\d{2}:\d{2}:\d{2})\s+(?P<host>\S+)\s+(?P<tag>[^:\s\[]+)(?:\[(?P<pid>\d+)\])?:\s*(?P<msg>.*)$"
)
RFC5424_RE = re.compile(
    r"^<(?P<pri>\d{1,3})>(?P<ver>\d+)\s+(?P<ts>\S+)\s+(?P<host>\S+)\s+"
    r"(?P<app>\S+)\s+(?P<proc>\S+)\s+(?P<msgid>\S+)\s+"
    r"(?:\[(?P<sd>[^\]]*)\])?\s*(?P<msg>.*)$"
)
MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}
LOGIN_KW = re.compile(r"(login|logon|auth(enticat)?ed|accepted)", re.IGNORECASE)
DENY_KW = re.compile(r"(deny|denied|reject|block|drop|fail(ed)?|invalid)", re.IGNORECASE)
PERMIT_KW = re.compile(r"(permit|allow|accept|pass)", re.IGNORECASE)
ERROR_KW = re.compile(r"(error|err|fatal|critical|alert|emergency)", re.IGNORECASE)


class SyslogParser(ILogParser):
    def can_parse(self, file_path: str, header_bytes: bytes, sample_lines: List[str]) -> bool:
        header_text = header_bytes.decode("utf-8", errors="replace")
        if re.match(r"^<\d{1,3}>", header_text, re.MULTILINE):
            return True
        for line in sample_lines[:20]:
            if RFC3164_RE.match(line) or RFC5424_RE.match(line):
                return True
        return False

    def _parse_timestamp_3164(self, mon: str, day: str, time_str: str) -> str:
        month = MONTHS.get(mon, 1)
        year = datetime.now().year
        try:
            dt = datetime(year, month, int(day),
                          *map(int, time_str.split(":")))
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return f"{mon} {day} {time_str}"

    def _parse_timestamp_5424(self, ts: str) -> str:
        try:
            if ts.endswith("Z"):
                ts = ts[:-1] + "+00:00"
            dt = datetime.fromisoformat(ts)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return ts

    def _classify(self, tag: str, msg: str) -> str:
        text = f"{tag} {msg}"
        if DENY_KW.search(text):
            return "deny"
        if LOGIN_KW.search(text):
            return "login"
        if PERMIT_KW.search(text):
            return "permit"
        if ERROR_KW.search(text):
            return "error"
        return "info"

    def parse(self, file_path: str) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        line_no = 0

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            for raw_line in f:
                line_no += 1
                line = raw_line.rstrip("\n")
                stripped = line.strip()
                if not stripped:
                    continue

                timestamp = None
                host = None
                tag = None
                msg = stripped
                pri = None

                m3164 = RFC3164_RE.match(stripped)
                if m3164:
                    pri = m3164.group("pri")
                    timestamp = self._parse_timestamp_3164(
                        m3164.group("mon"),
                        m3164.group("day"),
                        m3164.group("time"),
                    )
                    host = m3164.group("host")
                    tag = m3164.group("tag")
                    msg = m3164.group("msg")
                else:
                    m5424 = RFC5424_RE.match(stripped)
                    if m5424:
                        pri = m5424.group("pri")
                        timestamp = self._parse_timestamp_5424(m5424.group("ts"))
                        host = m5424.group("host")
                        tag = m5424.group("app")
                        msg = m5424.group("msg")

                ips = IPV4_RE.findall(msg)
                source_ip = ips[0] if len(ips) >= 1 else None
                target_ip = ips[1] if len(ips) >= 2 else None

                user_match = re.search(r"user(?:name)?[=:\s]+['\"]?(\S+?)['\"]?[\s,;)]", msg, re.IGNORECASE)
                user = user_match.group(1) if user_match else None

                event_type = self._classify(tag or "", msg)

                events.append({
                    "timestamp": timestamp,
                    "event_type": event_type,
                    "source_ip": source_ip,
                    "target_ip": target_ip,
                    "user": user,
                    "device": host,
                    "command": None,
                    "result": event_type,
                    "detail": msg,
                    "raw_line": stripped,
                    "line_no": line_no,
                    "_pri": pri,
                    "_tag": tag,
                })

        return events
