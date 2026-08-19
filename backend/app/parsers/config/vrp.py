import re
from typing import List, Dict, Any
from .base import IConfigParser


SECTION_KEYWORDS = [
    (re.compile(r"^\s*interface\s+GigabitEthernet", re.IGNORECASE), "interface"),
    (re.compile(r"^\s*interface\s+Vlanif", re.IGNORECASE), "interface"),
    (re.compile(r"^\s*interface\s+Eth-Trunk", re.IGNORECASE), "interface"),
    (re.compile(r"^\s*interface\s+LoopBack", re.IGNORECASE), "interface"),
    (re.compile(r"^\s*interface\s+NULL0", re.IGNORECASE), "interface"),
    (re.compile(r"^\s*interface\s+", re.IGNORECASE), "interface"),
    (re.compile(r"^\s*acl\s+number\s+", re.IGNORECASE), "acl"),
    (re.compile(r"^\s*acl\s+name\s+", re.IGNORECASE), "acl"),
    (re.compile(r"^\s*acl\s+advpool\s+", re.IGNORECASE), "acl"),
    (re.compile(r"^\s*acl\s+", re.IGNORECASE), "acl"),
    (re.compile(r"^\s*security-policy\b", re.IGNORECASE), "security_policy"),
    (re.compile(r"^\s*security-zone\b", re.IGNORECASE), "security_zone"),
    (re.compile(r"^\s*firewall\s+zone\b", re.IGNORECASE), "security_zone"),
    (re.compile(r"^\s*aaa\b", re.IGNORECASE), "aaa"),
    (re.compile(r"^\s*authentication-scheme\b", re.IGNORECASE), "aaa"),
    (re.compile(r"^\s*authorization-scheme\b", re.IGNORECASE), "aaa"),
    (re.compile(r"^\s*accounting-scheme\b", re.IGNORECASE), "aaa"),
    (re.compile(r"^\s*local-user\b", re.IGNORECASE), "aaa"),
    (re.compile(r"^\s*ssh\s+server\b", re.IGNORECASE), "ssh"),
    (re.compile(r"^\s*ssh\s+user\b", re.IGNORECASE), "ssh"),
    (re.compile(r"^\s*ssh\s+client\b", re.IGNORECASE), "ssh"),
    (re.compile(r"^\s*ssh\s+secure\b", re.IGNORECASE), "ssh"),
    (re.compile(r"^\s*ssh\s+compatible\b", re.IGNORECASE), "ssh"),
    (re.compile(r"^\s*user-interface\b", re.IGNORECASE), "management_line"),
    (re.compile(r"^\s*snmp-agent\b", re.IGNORECASE), "snmp"),
    (re.compile(r"^\s*telnet\s+server\b", re.IGNORECASE), "service"),
    (re.compile(r"^\s*http\s+server\b", re.IGNORECASE), "service"),
    (re.compile(r"^\s*https\s+server\b", re.IGNORECASE), "service"),
    (re.compile(r"^\s*ftp\s+server\b", re.IGNORECASE), "service"),
    (re.compile(r"^\s*dhcp\s+enable\b", re.IGNORECASE), "service"),
    (re.compile(r"^\s*stp\b", re.IGNORECASE), "l2"),
    (re.compile(r"^\s*vlan\s+\d", re.IGNORECASE), "l2"),
    (re.compile(r"^\s*bpdu\s+tunnel\b", re.IGNORECASE), "l2"),
    (re.compile(r"^\s*ospf\b", re.IGNORECASE), "routing"),
    (re.compile(r"^\s*bgp\b", re.IGNORECASE), "routing"),
    (re.compile(r"^\s*rip\b", re.IGNORECASE), "routing"),
    (re.compile(r"^\s*isis\b", re.IGNORECASE), "routing"),
    (re.compile(r"^\s*ip\s+route-static\b", re.IGNORECASE), "routing"),
    (re.compile(r"^\s*router\s+id\b", re.IGNORECASE), "routing"),
    (re.compile(r"^\s*nat-policy\b", re.IGNORECASE), "nat"),
    (re.compile(r"^\s*nat\s+server\b", re.IGNORECASE), "nat"),
    (re.compile(r"^\s*ip\s+vpn-instance\b", re.IGNORECASE), "vpn"),
    (re.compile(r"^\s*ipsec\b", re.IGNORECASE), "ipsec"),
    (re.compile(r"^\s*ike\s+peer\b", re.IGNORECASE), "ipsec"),
    (re.compile(r"^\s*ipsec\s+proposal\b", re.IGNORECASE), "ipsec"),
    (re.compile(r"^\s*ipsec\s+policy\b", re.IGNORECASE), "ipsec"),
    (re.compile(r"^\s*traffic-policy\b", re.IGNORECASE), "qos"),
    (re.compile(r"^\s*traffic\s+classifier\b", re.IGNORECASE), "qos"),
    (re.compile(r"^\s*traffic\s+behavior\b", re.IGNORECASE), "qos"),
    (re.compile(r"^\s*qos\b", re.IGNORECASE), "qos"),
    (re.compile(r"^\s*info-center\b", re.IGNORECASE), "log"),
    (re.compile(r"^\s*clock\s+timezone\b", re.IGNORECASE), "system"),
    (re.compile(r"^\s*sysname\b", re.IGNORECASE), "system"),
    (re.compile(r"^\s*ntp-service\b", re.IGNORECASE), "system"),
    (re.compile(r"^\s*header\b", re.IGNORECASE), "system"),
    (re.compile(r"^\s*password\s+header\b", re.IGNORECASE), "system"),
]

ANNOTATION_MAP = {
    "ip address": "配置接口IP地址和掩码",
    "description": "接口或对象描述",
    "sysname": "设置设备主机名",
    "password": "设置密码",
    "local-user": "创建本地用户",
    "state": "设置接口状态(up/down)",
    "shutdown": "关闭接口",
    "undo shutdown": "启用接口",
    "access-type": "指定用户接入类型",
    "privilege level": "配置用户权限级别",
    "service-type": "指定用户服务类型(ssh/telnet等)",
    "default authentication-scheme": "配置默认认证方案",
    "authentication-scheme": "配置认证方案",
    "authorization-scheme": "配置授权方案",
    "accounting-scheme": "配置计费方案",
    "vlan": "配置VLAN",
    "port default vlan": "设置接口默认VLAN",
    "port link-type": "设置接口链路类型(access/trunk/hybrid)",
    "trunk allow-pass vlan": "配置Trunk允许通过的VLAN",
    "rule": "配置ACL规则",
    "source-zone": "配置安全策略源安全区域",
    "destination-zone": "配置安全策略目的安全区域",
    "source-address": "配置安全策略源地址",
    "destination-address": "配置安全策略目的地址",
    "action": "配置动作(permit/deny)",
    "profile": "引用配置模板",
    "dhcp select": "配置DHCP模式",
    "dhcp server": "配置DHCP服务器参数",
    "dns resolve": "启用DNS解析",
    "dns server": "配置DNS服务器",
    "ip route-static": "配置静态路由",
    "stp": "配置生成树协议",
    "ntp-service": "配置NTP服务",
    "clock timezone": "配置时区",
    "header": "配置登录提示信息",
    "ftp server": "配置FTP服务器",
    "telnet server": "配置Telnet服务",
    "http server": "配置HTTP服务",
    "https server": "配置HTTPS服务",
    "info-center": "配置信息中心(日志)",
    "snmp-agent community": "配置SNMP团体名",
    "snmp-agent group": "配置SNMP用户组",
    "snmp-agent usm-user": "配置SNMP用户",
    "ssh server": "配置SSH服务器参数",
    "ssh user": "配置SSH用户",
    "ssh authentication-type": "配置SSH认证类型",
}

RISK_PATTERNS = [
    (re.compile(r"telnet\s+server\s+enable", re.IGNORECASE), "high", "Telnet服务以明文传输认证信息"),
    (re.compile(r"ssh\s+compatible-ssh1x", re.IGNORECASE), "high", "SSH兼容存在已知漏洞的SSH1.x协议"),
    (re.compile(r"ssh\s+server\s+dh-exchange\s+group\s+dh_group1", re.IGNORECASE), "high", "SSH使用弱密钥交换算法diffie-hellman-group1"),
    (re.compile(r"ssh\s+server\s+key-exchange\s+.*diffie-hellman-group1", re.IGNORECASE), "high", "SSH使用弱密钥交换算法diffie-hellman-group1"),
    (re.compile(r"ssh\s+server\s+cipher\s+.*(3des|des-cbc)", re.IGNORECASE), "medium", "SSH启用弱加密算法(3DES/DES)"),
    (re.compile(r"local-user\s+\S+\s+password\s+simple", re.IGNORECASE), "medium", "本地用户密码以明文方式配置"),
    (re.compile(r"snmp-agent\s+community\s+(read|write)\s+(public|private)\b", re.IGNORECASE), "medium", "SNMP使用默认团体名public/private"),
    (re.compile(r"snmp-agent\s+community\s+(public|private)\b", re.IGNORECASE), "medium", "SNMP使用默认团体名public/private"),
]


def _detect_section(line: str) -> str | None:
    for pattern, stype in SECTION_KEYWORDS:
        if pattern.match(line):
            return stype
    return None


def _annotate(key: str) -> str:
    if not key:
        return ""
    kl = key.strip().lower()
    for k, v in ANNOTATION_MAP.items():
        if kl.startswith(k.lower()):
            return v
    return ""


def _check_risk(line: str, section_type: str | None, items_in_section: List[Dict]) -> tuple[bool, str, str]:
    """返回 (is_risk, level, reason)"""
    for pat, level, reason in RISK_PATTERNS:
        if pat.search(line):
            return True, level, reason
    if section_type == "security_policy":
        has_source_zone = any("source-zone" in it.get("key", "") for it in items_in_section)
        has_source_addr = any("source-address" in it.get("key", "") for it in items_in_section)
        has_permit = any("permit" in (it.get("value", "") + it.get("key", "")).lower() for it in items_in_section)
        if has_permit and not has_source_zone and not has_source_addr:
            return True, "high", "安全策略permit动作但未配置源安全区域和源地址"
    return False, "", ""


class VRPConfigParser(IConfigParser):
    def can_parse(self, file_path: str, header_bytes: bytes, sample_lines: List[str]) -> bool:
        header_text = header_bytes.decode("utf-8", errors="replace")
        if "!CfgFileCrc" in header_text or "sysname " in header_text:
            return True
        joined = " ".join(sample_lines[:20])
        return bool(re.search(r"\bsysname\b", joined) or "!CfgFileCrc" in joined)

    def parse(self, file_path: str) -> Dict[str, Any]:
        device_name = None
        device_type = None
        vendor = "Huawei"
        software_version = None
        config_crc = None
        sections: List[Dict[str, Any]] = []

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        header_done = False
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            m = re.search(r"!CfgFileCrc\s*[:=]?\s*([0-9A-Fa-f]+)", line)
            if m:
                config_crc = m.group(1)
            m = re.search(r"\bVRP \(R\) software,?\s*Version\s+(\S+)", line, re.IGNORECASE)
            if m:
                software_version = m.group(1)
            m = re.search(r"\bversion\s+(\S+)", line, re.IGNORECASE)
            if m and software_version is None:
                software_version = m.group(1)
            m = re.match(r"^\s*sysname\s+(.+)$", line, re.IGNORECASE)
            if m:
                device_name = m.group(1).strip()
                header_done = True

        blocks: List[List[tuple[int, str]]] = []
        current_block: List[tuple[int, str]] = []
        for i, line in enumerate(lines):
            raw = line.rstrip("\n")
            stripped = raw.strip()
            # Treat both `#` and standalone `!` lines as separators in VRP (Huawei uses both)
            is_sep = stripped == "#" or stripped == "!"
            if is_sep:
                if current_block:
                    blocks.append(current_block)
                    current_block = []
            elif stripped and not stripped.startswith("!") and not stripped.startswith("//"):
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
            if len(words) >= 2 and section_type == "interface":
                section_name = " ".join(words[1:])
            elif len(words) >= 3 and section_type == "acl":
                section_name = " ".join(words[1:])
            elif len(words) >= 2 and section_type in ("routing",):
                section_name = " ".join(words[1:])
            else:
                section_name = first_stripped[:60]

            items: List[Dict[str, Any]] = []
            items_section_context: List[Dict] = []
            for line_no, raw_line in block:
                indent_spaces = len(raw_line) - len(raw_line.lstrip(" "))
                indent_level = indent_spaces // 2
                stripped = raw_line.strip()
                parts = stripped.split(" ", 1)
                key = parts[0] if parts else ""
                value = parts[1] if len(parts) > 1 else ""

                annotation = _annotate(key + (" " + value.split(" ", 1)[0] if value else ""))
                if not annotation:
                    annotation = _annotate(key)

                tmp_ctx = list(items_section_context)
                tmp_ctx.append({"key": key, "value": value, "line_no": line_no})
                is_risk, risk_level, risk_reason = _check_risk(stripped, section_type, tmp_ctx)
                if not is_risk:
                    items_section_context.append({"key": key, "value": value, "line_no": line_no})

                if annotation and risk_reason:
                    annotation = f"{annotation} | 风险提示: {risk_reason}"
                elif risk_reason:
                    annotation = f"风险提示: {risk_reason}"

                doc_ref = ""
                if section_type in ("interface", "acl", "security_policy", "ssh", "snmp", "aaa"):
                    doc_ref = f"VRP {section_type} 配置指南"

                items.append({
                    "line_no": line_no,
                    "raw_line": stripped,
                    "key": key,
                    "value": value,
                    "indent_level": indent_level,
                    "annotation": annotation,
                    "doc_ref": doc_ref,
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
