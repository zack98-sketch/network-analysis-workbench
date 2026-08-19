import re
from typing import List, Dict, Any
from .base import IConfigParser


class GenericConfigParser(IConfigParser):
    def can_parse(self, file_path: str, header_bytes: bytes, sample_lines: List[str]) -> bool:
        return True

    def parse(self, file_path: str) -> Dict[str, Any]:
        device_name = None
        vendor = None
        software_version = None
        config_crc = None
        sections: List[Dict[str, Any]] = []
        current_section_type = "system"
        current_section_name = "system"
        current_items: List[Dict[str, Any]] = []

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        for line in lines[:80]:
            if device_name is None:
                for kw in ("sysname", "hostname"):
                    m = re.match(r"^\s*" + kw + r"\s+(.+)$", line, re.IGNORECASE)
                    if m:
                        device_name = m.group(1).strip()
                        break
            if software_version is None:
                m = re.search(r"\bversion\s+(\S+)", line, re.IGNORECASE)
                if m:
                    software_version = m.group(1)
            m = re.search(r"Crc\s*[:=]?\s*([0-9A-Fa-f]{6,})", line)
            if m:
                config_crc = m.group(1)

        prev_indent = -1
        line_no = 0
        for raw_line in lines:
            line_no += 1
            stripped = raw_line.rstrip("\n")
            if not stripped.strip():
                continue
            if stripped.strip() in ("#", "!", ";"):
                if current_items:
                    sections.append({
                        "section_type": current_section_type,
                        "section_name": current_section_name,
                        "items": current_items,
                    })
                    current_items = []
                current_section_type = "system"
                current_section_name = "system"
                prev_indent = -1
                continue

            indent_spaces = len(stripped) - len(stripped.lstrip(" "))
            indent_level = indent_spaces // 2

            line_content = stripped.strip()
            parts = line_content.split(" ", 1)
            key = parts[0] if parts else ""
            value = parts[1] if len(parts) > 1 else ""

            if indent_level == 0 and prev_indent >= 0:
                if current_items:
                    sections.append({
                        "section_type": current_section_type,
                        "section_name": current_section_name,
                        "items": current_items,
                    })
                    current_items = []
                current_section_type = key.lower() if key else "system"
                current_section_name = line_content[:60]

            current_items.append({
                "line_no": line_no,
                "raw_line": line_content,
                "key": key,
                "value": value,
                "indent_level": indent_level,
                "annotation": "",
                "doc_ref": "",
                "is_risk": False,
                "risk_level": "",
            })
            prev_indent = indent_level

        if current_items:
            sections.append({
                "section_type": current_section_type,
                "section_name": current_section_name,
                "items": current_items,
            })

        if device_name and vendor is None:
            if any(s["section_type"] == "snmp-agent" or "snmp-agent" in s["section_name"] for s in sections):
                vendor = "Huawei"
            elif any(s["section_type"] == "snmp-server" or "snmp-server" in s["section_name"] for s in sections):
                vendor = "Cisco"

        return {
            "device_name": device_name,
            "device_type": None,
            "vendor": vendor,
            "software_version": software_version,
            "config_crc": config_crc,
            "sections": sections,
        }
