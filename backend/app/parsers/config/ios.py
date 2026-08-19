import re
from typing import List, Dict, Any
from .base import IConfigParser


SECTION_KEYWORDS = [
    (re.compile(r"^\s*interface\s+", re.IGNORECASE), "interface"),
    (re.compile(r"^\s*access-list\s+", re.IGNORECASE), "acl"),
    (re.compile(r"^\s*ip\s+access-list\s+", re.IGNORECASE), "acl"),
    (re.compile(r"^\s*line\s+vty\s+", re.IGNORECASE), "line"),
    (re.compile(r"^\s*line\s+console\s+", re.IGNORECASE), "line"),
    (re.compile(r"^\s*router\s+", re.IGNORECASE), "routing"),
    (re.compile(r"^\s*snmp-server\s+", re.IGNORECASE), "snmp"),
    (re.compile(r"^\s*aaa\b", re.IGNORECASE), "aaa"),
    (re.compile(r"^\s*username\b", re.IGNORECASE), "aaa"),
    (re.compile(r"^\s*enable\s+", re.IGNORECASE), "aaa"),
    (re.compile(r"^\s*ip\s+nat\b", re.IGNORECASE), "nat"),
    (re.compile(r"^\s*ip\s+dhcp\b", re.IGNORECASE), "dhcp"),
    (re.compile(r"^\s*ip\s+route\b", re.IGNORECASE), "routing"),
    (re.compile(r"^\s*logging\b", re.IGNORECASE), "logging"),
    (re.compile(r"^\s*service\b", re.IGNORECASE), "service"),
    (re.compile(r"^\s*vlan\s+", re.IGNORECASE), "vlan"),
]

RISK_PATTERNS = [
    (re.compile(r"transport\s+input\s+telnet", re.IGNORECASE), "high", "VTY线路允许明文Telnet接入"),
    (re.compile(r"snmp-server\s+community\s+(public|private)\b", re.IGNORECASE), "medium", "SNMP使用默认团体名public/private"),
    (re.compile(r"enable\s+password\s+(?!secret)", re.IGNORECASE), "medium", "enable密码使用弱加密方式(type 7)"),
    (re.compile(r"username\s+\S+\s+password\s+(?!secret)", re.IGNORECASE), "medium", "用户密码使用弱加密方式(type 7)"),
    (re.compile(r"no\s+service\s+password-encryption", re.IGNORECASE), "medium", "未启用密码加密服务"),
    (re.compile(r"ip\s+http\s+server\b", re.IGNORECASE), "medium", "启用明文HTTP管理服务"),
]


def _detect_section(line: str) -> str | None:
    for pattern, stype in SECTION_KEYWORDS:
        if pattern.match(line):
            return stype
    return None


class IOSConfigParser(IConfigParser):
    def can_parse(self, file_path: str, header_bytes: bytes, sample_lines: List[str]) -> bool:
        header_text = header_bytes.decode("utf-8", errors="replace")
        joined = " ".join(sample_lines[:20])
        text = header_text + joined
        has_hostname = bool(re.search(r"^\s*hostname\s+", text, re.MULTILINE))
        has_version = bool(re.search(r"\bversion\s+\d+\.\d+", text))
        has_bang = any(s.strip() == "!" for s in sample_lines[:30])
        return has_hostname or (has_version and has_bang)

    def parse(self, file_path: str) -> Dict[str, Any]:
        device_name = None
        device_type = None
        vendor = "Cisco"
        software_version = None
        config_crc = None
        sections: List[Dict[str, Any]] = []

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        for line in lines[:50]:
            m = re.search(r"\bversion\s+(\d+\.\d+(?:\(\d+\))?[A-Za-z0-9]*)", line, re.IGNORECASE)
            if m:
                software_version = m.group(1)
            m = re.match(r"^\s*hostname\s+(.+)$", line, re.IGNORECASE)
            if m:
                device_name = m.group(1).strip()

        blocks: List[List[tuple[int, str]]] = []
        current_block: List[tuple[int, str]] = []
        for i, line in enumerate(lines):
            raw = line.rstrip("\n")
            stripped = raw.strip()
            if stripped == "!":
                if current_block:
                    blocks.append(current_block)
                    current_block = []
            elif stripped and not stripped.startswith("!") and not stripped.startswith("#"):
                current_block.append((i + 1, raw))
        if current_block:
            blocks.append(current_block)

        for block in blocks:
            if not block:
                continue
            first_line_no, first_line_raw = block[0]
            first_stripped = first_line_raw.strip()
            section_type = _detect_section(first_stripped) or "system"

            words = first_stripped.split()
            if len(words) >= 2:
                section_name = " ".join(words[1:])
            else:
                section_name = first_stripped[:60]

            items: List[Dict[str, Any]] = []
            items_ctx: List[Dict] = []
            for line_no, raw_line in block:
                indent_spaces = len(raw_line) - len(raw_line.lstrip(" "))
                indent_level = indent_spaces // 2
                stripped = raw_line.strip()
                parts = stripped.split(" ", 1)
                key = parts[0] if parts else ""
                value = parts[1] if len(parts) > 1 else ""

                is_risk = False
                risk_level = ""
                for pat, level, reason in RISK_PATTERNS:
                    if pat.search(stripped):
                        is_risk = True
                        risk_level = f"{level}: {reason}"
                        break

                items_ctx.append({"key": key, "value": value})
                items.append({
                    "line_no": line_no,
                    "raw_line": stripped,
                    "key": key,
                    "value": value,
                    "indent_level": indent_level,
                    "annotation": "",
                    "doc_ref": "",
                    "is_risk": is_risk,
                    "risk_level": risk_level,
                })

            sections.append({
                "section_type": section_type,
                "section_name": section_name,
                "items": items,
            })

        return {
            "device_name": device_name,
            "device_type": device_type,
            "vendor": vendor,
            "software_version": software_version,
            "config_crc": config_crc,
            "sections": sections,
        }
