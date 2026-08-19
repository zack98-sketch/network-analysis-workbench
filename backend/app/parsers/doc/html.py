import re
from typing import List, Dict, Any
from .base import IDocIndexer


CONFIG_KEYWORDS = [
    "security-policy", "nat-policy", "acl", "firewall",
    "interface", "GigabitEthernet", "Vlanif", "vlan",
    "ssh", "snmp-agent", "snmp-server", "telnet",
    "ospf", "bgp", "rip", "isis", "ip route",
    "nat", "dhcp", "dns", "ntp-service",
    "aaa", "local-user", "authentication",
    "vpn-instance", "ipsec",
]


def _extract_keywords(text: str) -> str:
    found = set()
    for kw in CONFIG_KEYWORDS:
        pattern = re.compile(r"\b" + re.escape(kw) + r"\b", re.IGNORECASE)
        if pattern.search(text):
            found.add(kw.lower())
    return ", ".join(sorted(found))


class HTMLIndexer(IDocIndexer):
    def can_parse(self, file_path: str, header_bytes: bytes, sample_lines: List[str]) -> bool:
        header = header_bytes.decode("utf-8", errors="replace").lower()
        return "<!doctype html" in header or "<html" in header

    def parse(self, file_path: str) -> List[Dict[str, Any]]:
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            return []

        docs: List[Dict[str, Any]] = []
        title = None
        section_stack: List[tuple[int, str]] = []
        page_no = 1

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        soup = BeautifulSoup(content, "html.parser")

        title_tag = soup.find("title")
        if title_tag and title_tag.get_text():
            title = title_tag.get_text().strip()

        text_parts = []
        for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "pre", "li", "div"]):
            if tag.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
                if text_parts and (section_stack or docs):
                    combined_text = "\n".join(text_parts)
                    section_path = " > ".join([s[1] for s in section_stack])
                    docs.append({
                        "title": title,
                        "section_path": section_path,
                        "content_text": combined_text.strip(),
                        "config_keywords": _extract_keywords(combined_text),
                        "page_no": page_no,
                    })
                    text_parts = []

                level = int(tag.name[1])
                heading_text = tag.get_text().strip()
                while section_stack and section_stack[-1][0] >= level:
                    section_stack.pop()
                section_stack.append((level, heading_text))
                if not title:
                    title = heading_text
            else:
                t = tag.get_text().strip()
                if t:
                    text_parts.append(t)

        if text_parts:
            combined_text = "\n".join(text_parts)
            section_path = " > ".join([s[1] for s in section_stack])
            docs.append({
                "title": title,
                "section_path": section_path,
                "content_text": combined_text.strip(),
                "config_keywords": _extract_keywords(combined_text),
                "page_no": page_no,
            })

        return docs
