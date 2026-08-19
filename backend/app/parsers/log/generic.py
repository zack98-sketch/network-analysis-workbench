import re
from typing import List, Dict, Any
from .base import ILogParser


IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
TS_FULL_RE = re.compile(r"\d{4}[-/]\d{2}[-/]\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?")
TS_HMS_RE = re.compile(r"\b\d{2}:\d{2}:\d{2}\b")
LOGIN_KW = re.compile(r"(login|logon|auth|accepted)", re.IGNORECASE)
DENY_KW = re.compile(r"(deny|denied|reject|block|drop|fail(ed)?|invalid)", re.IGNORECASE)
PERMIT_KW = re.compile(r"(permit|allow|accept|pass)", re.IGNORECASE)
ERROR_KW = re.compile(r"(error|err|fatal|critical|alert)", re.IGNORECASE)
CMD_KW = re.compile(r"^[<\[]?[A-Za-z0-9_\-\.]+[>\]]?\s+[A-Za-z][A-Za-z0-9\-]+\s")


def _extract_timestamp(line: str) -> str | None:
    m = TS_FULL_RE.search(line)
    if m:
        return m.group(0).replace("/", "-").replace("T", " ")
    m = TS_HMS_RE.search(line)
    if m:
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        return f"{today} {m.group(0)}"
    return None


def _classify(line: str) -> str:
    if DENY_KW.search(line):
        return "deny"
    if LOGIN_KW.search(line):
        return "login"
    if PERMIT_KW.search(line):
        return "permit"
    if ERROR_KW.search(line):
        return "error"
    if CMD_KW.match(line):
        return "command"
    return "info"


class GenericLogParser(ILogParser):
    def can_parse(self, file_path: str, header_bytes: bytes, sample_lines: List[str]) -> bool:
        return True

    def parse(self, file_path: str) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        current: Dict[str, Any] | None = None
        line_no = 0

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            for raw_line in f:
                line_no += 1
                line = raw_line.rstrip("\n")
                stripped = line.strip()
                if not stripped:
                    continue

                ts = _extract_timestamp(stripped)
                ips = IPV4_RE.findall(stripped)

                is_new_event = ts is not None
                if not is_new_event and current is None:
                    is_new_event = True

                if is_new_event:
                    if current is not None:
                        events.append(current)
                    src_ip = ips[0] if len(ips) >= 1 else None
                    dst_ip = ips[1] if len(ips) >= 2 else None
                    event_type = _classify(stripped)
                    current = {
                        "timestamp": ts,
                        "event_type": event_type,
                        "source_ip": src_ip,
                        "target_ip": dst_ip,
                        "user": None,
                        "device": None,
                        "command": None,
                        "result": None,
                        "detail": stripped,
                        "raw_line": stripped,
                        "line_no": line_no,
                    }
                else:
                    if current is not None:
                        current["detail"] = (current["detail"] or "") + "\n" + stripped
                        if not current["source_ip"] and ips:
                            current["source_ip"] = ips[0]
                        if not current["target_ip"] and len(ips) >= 2:
                            current["target_ip"] = ips[1]

        if current is not None:
            events.append(current)

        return events
