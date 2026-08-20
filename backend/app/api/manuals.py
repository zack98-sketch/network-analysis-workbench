"""Manipulate the *background dictionary library* of operation manuals.

These manuals are global knowledge base entries. They do NOT belong to a
specific project and are NOT the same thing as user-uploaded doc materials.
Think of them as built-in or admin-maintained CLI/protocol/log-pattern docs.
"""
from datetime import datetime
from typing import Optional, List, Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, or_, func, cast, String
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.doc_index import DocIndex
from app.models.manual import Manual, ManualCategory, MappingTarget


router = APIRouter()


# ------------------------ Legacy DocIndex endpoints -------------------------
class DocSection(BaseModel):
    id: Optional[int] = None
    material_id: Optional[int] = None
    title: Optional[str] = None
    section_path: Optional[str] = None
    content_text: Optional[str] = None
    config_keywords: Optional[str] = None
    page_no: Optional[int] = None

    class Config:
        from_attributes = True


class SearchQuery(BaseModel):
    query: str
    project_id: Optional[int] = None
    material_id: Optional[int] = None
    top_k: int = 10


class SearchHit(BaseModel):
    score: float
    section: DocSection


class SearchResponse(BaseModel):
    query: str
    hits: List[SearchHit]
    total: int


@router.post("/manuals/search", response_model=SearchResponse)
async def search_manuals(payload: SearchQuery, db: AsyncSession = Depends(get_db)):
    return SearchResponse(query=payload.query, hits=[], total=0)


@router.get("/projects/{project_id}/manuals/search", response_model=List[DocSection])
async def search_project_manuals(
    project_id: int,
    q: str = Query(default=""),
    db: AsyncSession = Depends(get_db),
):
    from app.models.material import Material
    mat_stmt = select(Material.id).where(Material.project_id == project_id)
    mat_res = await db.execute(mat_stmt)
    material_ids = [row[0] for row in mat_res.all()]

    if not material_ids:
        return []

    doc_stmt = select(DocIndex).where(DocIndex.material_id.in_(material_ids))
    if q:
        doc_stmt = doc_stmt.where(
            (DocIndex.title.ilike(f"%{q}%"))
            | (DocIndex.content_text.ilike(f"%{q}%"))
            | (DocIndex.config_keywords.ilike(f"%{q}%"))
        )
    doc_stmt = doc_stmt.limit(50)
    res = await db.execute(doc_stmt)
    return [DocSection.model_validate(d) for d in res.scalars().all()]


@router.get("/materials/{material_id}/doc-sections", response_model=List[DocSection])
async def list_material_doc_sections(
    material_id: int,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(DocIndex).where(DocIndex.material_id == material_id)
    res = await db.execute(stmt)
    return [DocSection.model_validate(d) for d in res.scalars().all()]


# ============== Global Manual Dictionary Library (后台字典) ==================

CATEGORY_LABEL = {
    "command_reference": "命令参考",
    "protocol_reference": "协议/端口标准",
    "config_pattern": "配置结构参考",
    "log_pattern": "日志结构参考",
    "compliance_baseline": "合规基线",
    "troubleshooting": "排障手册",
    "vendor_notes": "厂商注意事项",
}

MAPPING_LABEL = {
    "config_parser": "配置解析依据",
    "log_parser": "日志解析依据",
    "both": "双解析依据",
}


class ManualCreate(BaseModel):
    title: str
    category: str = "config_pattern"
    vendor: Optional[str] = None
    device_family: Optional[str] = None
    os_version: Optional[str] = None
    mapping_target: Optional[str] = None
    trigger_keywords: Optional[List[str]] = None
    signature_patterns: Optional[List[str]] = None
    summary: Optional[str] = None
    content_md: str = ""
    references: Optional[List[str]] = None
    standard_ref: Optional[str] = None


class ManualUpdate(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    vendor: Optional[str] = None
    device_family: Optional[str] = None
    os_version: Optional[str] = None
    mapping_target: Optional[str] = None
    trigger_keywords: Optional[List[str]] = None
    signature_patterns: Optional[List[str]] = None
    summary: Optional[str] = None
    content_md: Optional[str] = None
    references: Optional[List[str]] = None
    standard_ref: Optional[str] = None


class ManualRead(BaseModel):
    id: int
    title: str
    category: str
    vendor: Optional[str] = None
    device_family: Optional[str] = None
    os_version: Optional[str] = None
    mapping_target: Optional[str] = None
    trigger_keywords: Optional[List[str]] = None
    signature_patterns: Optional[List[str]] = None
    summary: Optional[str] = None
    content_md: str
    references: Optional[List[str]] = None
    standard_ref: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


def _enum_or(val, klass, default=None):
    if val is None:
        return default
    if isinstance(val, klass):
        return val
    try:
        return klass(str(val))
    except Exception:
        return default


def _to_read(m: Manual) -> ManualRead:
    def to_str(e):
        return e.value if hasattr(e, "value") else (str(e) if e is not None else None)

    return ManualRead(
        id=m.id,
        title=m.title,
        category=to_str(m.category) or "config_pattern",
        vendor=m.vendor,
        device_family=m.device_family,
        os_version=m.os_version,
        mapping_target=to_str(m.mapping_target),
        trigger_keywords=list(m.trigger_keywords) if isinstance(m.trigger_keywords, list) else m.trigger_keywords,
        signature_patterns=list(m.signature_patterns) if isinstance(m.signature_patterns, list) else m.signature_patterns,
        summary=m.summary,
        content_md=m.content_md or "",
        references=list(m.references) if isinstance(m.references, list) else m.references,
        standard_ref=m.standard_ref,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


@router.get("/dictionaries/manuals/categories")
async def list_dictionary_categories():
    return {
        "categories": [
            {"value": k, "label": v} for k, v in CATEGORY_LABEL.items()
        ],
        "mapping_targets": [
            {"value": k, "label": v} for k, v in MAPPING_LABEL.items()
        ],
    }


@router.get("/dictionaries/manuals/{manual_id}", response_model=ManualRead)
async def get_dictionary_manual(manual_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(Manual).where(Manual.id == manual_id)
    res = await db.execute(stmt)
    m = res.scalar_one_or_none()
    if m is None:
        raise HTTPException(status_code=404, detail="Dictionary entry not found")
    return _to_read(m)


@router.post("/dictionaries/manuals", response_model=ManualRead, status_code=status.HTTP_201_CREATED)
async def create_dictionary_manual(payload: ManualCreate, db: AsyncSession = Depends(get_db)):
    m = Manual(
        title=payload.title,
        category=_enum_or(payload.category, ManualCategory, ManualCategory.CONFIG_PATTERN),
        vendor=payload.vendor,
        device_family=payload.device_family,
        os_version=payload.os_version,
        mapping_target=_enum_or(payload.mapping_target, MappingTarget),
        trigger_keywords=payload.trigger_keywords,
        signature_patterns=payload.signature_patterns,
        summary=payload.summary,
        content_md=payload.content_md or "",
        references=payload.references,
        standard_ref=payload.standard_ref,
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return _to_read(m)


@router.put("/dictionaries/manuals/{manual_id}", response_model=ManualRead)
async def update_dictionary_manual(manual_id: int, payload: ManualUpdate, db: AsyncSession = Depends(get_db)):
    stmt = select(Manual).where(Manual.id == manual_id)
    res = await db.execute(stmt)
    m = res.scalar_one_or_none()
    if m is None:
        raise HTTPException(status_code=404, detail="Dictionary entry not found")
    for field in ("title", "vendor", "device_family", "os_version",
                  "trigger_keywords", "signature_patterns",
                  "summary", "content_md", "references", "standard_ref"):
        val = getattr(payload, field, None)
        if val is not None:
            setattr(m, field, val)
    if payload.category is not None:
        m.category = _enum_or(payload.category, ManualCategory, m.category)
    if payload.mapping_target is not None:
        m.mapping_target = _enum_or(payload.mapping_target, MappingTarget)
    await db.commit()
    await db.refresh(m)
    return _to_read(m)


@router.delete("/dictionaries/manuals/{manual_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dictionary_manual(manual_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(Manual).where(Manual.id == manual_id)
    res = await db.execute(stmt)
    m = res.scalar_one_or_none()
    if m is None:
        raise HTTPException(status_code=404, detail="Dictionary entry not found")
    await db.delete(m)
    await db.commit()
    return None


# =================== Key pairing (解析依据配对) =============================

class PairingRequest(BaseModel):
    q: str
    mapping_target: Optional[str] = None  # config_parser | log_parser | both


class PairingHit(BaseModel):
    manual_id: int
    title: str
    category: str
    vendor: Optional[str]
    mapping_target: Optional[str]
    summary: Optional[str]
    score: float
    matched_keywords: List[str]
    snippet: Optional[str]


@router.post("/dictionaries/manuals/_pair", response_model=List[PairingHit])
async def pair_parsing_reference(payload: PairingRequest, db: AsyncSession = Depends(get_db)):
    """Given a raw line / config key / log event text, find the Manual entries
    that best explain it. Used by the UI as「解析依据」/「查字典」button.
    """
    q = (payload.q or "").strip()
    if not q:
        return []

    stmt = select(Manual)
    if payload.mapping_target:
        stmt = stmt.where(Manual.mapping_target == _enum_or(payload.mapping_target, MappingTarget))
    # SQLite: keyword list is JSON array; do a LIKE cast + ilike text search
    like = f"%{q}%"
    stmt = stmt.where(or_(
        Manual.title.ilike(like),
        Manual.summary.ilike(like),
        Manual.content_md.ilike(like),
        cast(Manual.trigger_keywords, String).ilike(like),
    )).limit(20)
    res = await db.execute(stmt)
    candidates = list(res.scalars().all())

    q_tokens = [t for t in _tokenize(q) if len(t) >= 2]
    hits: List[PairingHit] = []
    for m in candidates:
        score = 0.0
        matched: List[str] = []
        tks = m.trigger_keywords if isinstance(m.trigger_keywords, list) else []
        # Pre-match on trigger keywords
        for tk in tks:
            if not isinstance(tk, str):
                continue
            if tk and (tk.lower() in q.lower() or q.lower() in tk.lower()):
                score += 8.0
                matched.append(tk)
        # Text overlap scoring
        joined = "\n".join(filter(None, [
            m.title or "",
            m.summary or "",
            m.content_md or "",
        ])).lower()
        for tok in q_tokens:
            if tok.lower() in joined:
                score += 1.0
                if tok.lower() not in matched:
                    matched.append(tok.lower())
        # title exact match bonus
        if m.title and q.lower() in (m.title or "").lower():
            score += 6.0
        if score <= 0:
            continue
        # Produce snippet from content_md
        snippet = _make_snippet(m.content_md or m.summary or "", q)
        mapping_target_val = m.mapping_target.value if hasattr(m.mapping_target, "value") else (str(m.mapping_target) if m.mapping_target else None)
        category_val = m.category.value if hasattr(m.category, "value") else str(m.category)
        hits.append(PairingHit(
            manual_id=m.id,
            title=m.title,
            category=category_val,
            vendor=m.vendor,
            mapping_target=mapping_target_val,
            summary=m.summary,
            score=round(score, 2),
            matched_keywords=matched[:20],
            snippet=snippet,
        ))
    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:10]


def _tokenize(text: str) -> List[str]:
    import re
    # Keep Chinese runs, ASCII identifiers/numbers, and protocol words
    tokens = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z_][A-Za-z0-9_-]{1,}|\d{2,}", text)
    return tokens


def _make_snippet(text: str, q: str, radius: int = 60) -> Optional[str]:
    if not text:
        return None
    idx = text.lower().find(q.lower())
    if idx < 0:
        # fallback: take first ~radius*2 chars
        clipped = text.strip().replace("\n", " ")
        return clipped[: radius * 2] + ("…" if len(clipped) > radius * 2 else "")
    start = max(0, idx - radius)
    end = min(len(text), idx + len(q) + radius)
    snippet = text[start:end].replace("\n", " ")
    if start > 0:
        snippet = "…" + snippet
    if end < len(text):
        snippet = snippet + "…"
    return snippet


# ============ Seed: bootstrap a minimal built-in dictionary ================

#: Used on first /dictionaries/manuals GET if the table is empty.
SEED_MANUALS: List[Dict[str, Any]] = [
    dict(
        title="华为 VRP AAA 本地用户配置结构",
        category="config_pattern",
        vendor="Huawei",
        device_family="AR/CE/S",
        os_version="VRP V8R10",
        mapping_target="config_parser",
        trigger_keywords=["aaa", "local-user", "authentication-scheme", "authentication-mode", "password simple", "password cipher", "privilege level"],
        summary="VRP 系统在 `aaa` 视图下通过 `local-user` 定义本地账号、`authentication-scheme` 指定认证模式；明文保存密码属高危配置。",
        content_md="""## AAA 视图 (VRP)
```
[Device] aaa
[Device-aaa] local-user demo-user password cipher <pwd> privilege level 15
[Device-aaa] authentication-scheme sch01
[Device-aaa-authen-sch01] authentication-mode local
```

### 解析约定（配置解析依据）
- 进入 `aaa` 视图后，每行 `local-user <name> password <simple|cipher> ...` 归属 `authentication` 模块，section_name=`aaa`。
- 关键字段：
  - `password simple` → 明文存储密码（RISK 中危）
  - `password cipher` → 密文存储（合规）
  - `privilege level 15` → 管理员级别
- 解析器若遇到 `local-user` 但未出现 `password`，应标记为 *不完整账号* 并在解析消息中提示。
""",
        references=["https://support.huawei.com/enterprise/zh/category/switches-pid-10097100?category=product"],
        standard_ref="GB/T 22239-2019 8.1.3 身份鉴别",
    ),
    dict(
        title="华为防火墙 会话日志 CSV 字段约定",
        category="log_pattern",
        vendor="Huawei",
        device_family="USG/Eudemon",
        mapping_target="log_parser",
        trigger_keywords=["session", "flow", "traffic", "destination_port", "src_ip", "dst_ip", "action", "permit", "deny", "bytes", "protocol", "CSV"],
        summary="防火墙会话/流量 CSV 日志字段约定，解析器依此映射到 LogEvent：timestamp/source_ip/target_ip/destination_port/_protocol/_bytes/event_type=traffic。",
        content_md="""## CSV 列名（大小写不敏感，支持中文别名）
| 推荐列名         | 内部字段             | 说明                                    |
|------------------|----------------------|-----------------------------------------|
| timestamp        | timestamp            | 起始/结束时间                          |
| source_ip/src_ip | LogEvent.source_ip   | 源 IP                                   |
| destination_ip/dst_ip/target_ip | target_ip     | 目标 IP                                 |
| destination_port/dst_port/dport | destination_port | 目标端口 |
| protocol/proto   | _protocol            | TCP/UDP/ICMP/…                          |
| action/result    | event_type + result  | permit=permit / deny=deny               |
| bytes            | _bytes               | 总字节数                                |

### 缺失字段处理
- 仅包含 `dst_ip` 时，解析器自动等价映射到 `target_ip`。
- `destination_port` 数字列缺失时，LogEvent.destination_port 置 NULL 并在 message 中提示。
""",
    ),
    dict(
        title="危险端口标准表（常见明文/高危协议）",
        category="protocol_reference",
        mapping_target="both",
        trigger_keywords=["telnet 23", "21 ftp", "69 tftp", "http 80", "snmp 161", "rdp 3389", "危险端口"],
        summary="列出常见明文或高危服务端口，配置核查和流量审核均以其作为告警触发基准。",
        content_md="""## 高危端口
| Port | 协议  | 风险 |
|------|-------|------|
| 21   | FTP   | 明文传输账号密码 |
| 23   | Telnet| 明文会话，极易嗅探（RISK: HIGH） |
| 69   | TFTP  | 无鉴权文件传输 |
| 80   | HTTP  | 明文 Web |
| 161  | SNMP v1/v2 | 团体名明文 |
| 3389 | RDP   | 暴露公网易被爆破 |

### 在审核引擎中的使用
- 配置审核：若看到 `telnet server enable` 或 `http server enable`，直接触发 HIGH。
- 流量审核：若出现 TCP/23 外联到公网 IP，判定为「被控主机外联 Telnet」风险。
""",
        standard_ref="GB/T 22239-2019 8.2.2 访问控制",
    ),
    dict(
        title="暴力登录检测（登录失败阈值规则）",
        category="log_pattern",
        mapping_target="log_parser",
        trigger_keywords=["login", "logon", "fail", "登录失败", "brute force", "暴力破解", "认证失败"],
        summary="5 分钟窗口内同一源 IP 对同一设备 ≥5 次登录失败 → 判定为暴力破解（RISK: HIGH）。",
        content_md="""## 判定公式
```
count(event_type in {login, auth, logon} AND result=fail)
  GROUP BY (source_ip, target_ip, 5min_bucket) >= 5
    => RISK brute_force_attack HIGH
```

### 日志解析器配套要求
- 登录事件必须写 `event_type = login`（大小写不敏感，解析器内部会转小写）。
- 登录成功写 `result = success`；登录失败写 `result = fail`。
- 所有登录事件推荐填写 `user` 字段，用于关联「凭据泄露（同帐户多 IP 登录）」子规则。
""",
        standard_ref="GB/T 22239-2019 8.1.4 登录失败处理",
    ),
    # ----- 华为官方产品文档嵌入（操作手册字典库 / 本地词典） -----
    dict(
        title="华为 ASG 防火墙显示类命令参考（V300R022C00）",
        category="command_reference",
        vendor="Huawei",
        device_family="ASG-D/ASG-E/ASG5000",
        os_version="V300R022C00",
        mapping_target="config_parser",
        trigger_keywords=[
            "display address", "display address-group", "display application bypass info", "display arp",
            "display audit_policy accelerate", "display bridge-group", "display capacity", "display config-list",
            "display cpu usage", "display current-config", "display date", "display debugging all",
            "display dp drop statistics", "display dp memory", "display dp state", "display flowfast state",
            "display ha config diff", "display ha state", "display hardware info", "display http_file_cache statistic info",
            "display https-portal new-connection detail", "display ike sa", "display interface",
            "display ip defend drop info", "display ip interface brief", "display ip ospf", "display ip rip",
            "display ip route", "display ip session", "display ipsec sa", "display ipv6",
            "display ldap-auth easy-name-match switch", "display lldp local-information",
            "display lldp neighbor-information", "display lldp statistics", "display log statistics",
            "display memory-usage", "display nat-policy", "display policy accelerate",
            "display qos-profile", "display qos-profile statistics", "display statistics",
            "display sslproxy-optimize switch", "display tcpstack connection all",
            "display tcpstack connection source-ip", "display tcpstack switch", "display tdma user-net",
            "display update-http-proxy", "display user-auth whitelist cache", "display user-manage online-user",
            "display user-share", "display user-waa", "display version",
            "ASG", "ASG-D", "ASG-E", "ASG5000", "华为防火墙", "应用安全网关",
        ],
        summary="华为 ASG 系列（ASG-D/ASG-E/ASG5000）V300R022C00 全部显示类（display）命令清单，覆盖地址、策略、会话、路由、VPN、HA、硬件、用户认证等审计高频场景。来源于华为官方产品文档 EDOC1100313731。",
        content_md="""## 华为 ASG 防火墙显示类命令（V300R022C00）

来源：HUAWEI ASG-D, ASG-E, ASG5000 V300R022C00 产品文档（EDOC1100313731）
章节：命令参考 → 显示类命令
原文：<https://support.huawei.com/hedex/hdx.do?docid=EDOC1100313731&id=ZH-CN_TOPIC_0000001314006092>

### 系统与版本
| 命令 | 说明 |
|------|------|
| `display version` | 设备软件版本与启动信息 |
| `display date` | 系统时间 |
| `display current-config` | 当前生效配置 |
| `display config-list` | 配置变更列表 |

### 地址与安全策略
| 命令 | 说明 |
|------|------|
| `display address` | 地址对象 |
| `display address-group` | 地址组 |
| `display audit_policy accelerate` | 审计策略加速状态 |
| `display nat-policy` | NAT 策略 |
| `display policy accelerate` | 安全策略加速状态 |
| `display qos-profile` | QoS Profile |
| `display qos-profile statistics` | QoS 统计 |
| `display qos-profile NAME sfq` | 指定 QoS 的 SFQ |

### 会话与流量
| 命令 | 说明 |
|------|------|
| `display ip session` | IPv4 会话表 |
| `display statistics` | 流量统计 |
| `display flowfast state` | FlowFast 状态 |
| `display tcpstack connection all` | 所有 TCP 连接 |
| `display tcpstack connection source-ip <IP>` | 按源 IP 查看 TCP 连接 |
| `display tcpstack switch` | TCP 协议栈优化开关 |
| `display sslproxy-optimize switch` | SSL 代理优化开关 |
| `display https-portal new-connection detail` | HTTPS Portal 新连接详情 |

### 路由与接口
| 命令 | 说明 |
|------|------|
| `display ip route` | IPv4 路由表 |
| `display ip ospf` | OSPF 邻居与状态 |
| `display ip rip` | RIP 路由 |
| `display ip interface brief` | 接口 IP 简要信息 |
| `display interface` | 接口详细信息 |
| `display arp` | ARP 表 |
| `display ipv6` | IPv6 相关信息 |

### VPN（IKE / IPSec）
| 命令 | 说明 |
|------|------|
| `display ike sa` | IKE SA |
| `display ipsec sa` | IPSec SA |

### 用户与认证
| 命令 | 说明 |
|------|------|
| `display user-manage online-user` | 在线用户 |
| `display user-auth whitelist cache` | 用户认证白名单缓存 |
| `display user-share` | 用户共享信息 |
| `display user-waa` | 用户 WAA |
| `display ldap-auth easy-name-match switch` | LDAP 认证易名匹配开关 |

### HA 与硬件
| 命令 | 说明 |
|------|------|
| `display ha config diff` | HA 配置差异 |
| `display ha state` | HA 状态 |
| `display hardware info` | 硬件信息 |
| `display capacity` | 设备容量 |
| `display cpu usage` | CPU 使用率 |
| `display memory-usage` | 内存使用率 |
| `display dp drop statistics` | 数据面丢包统计 |
| `display dp memory` | 数据面内存 |
| `display dp state` | 数据面状态 |
| `display ip defend drop info` | IP 防御丢包信息 |
| `display log statistics` | 日志统计 |
| `display bridge-group` | 桥组 |
| `display application bypass info` | 应用绕过信息 |
| `display lldp local-information` | LLDP 本地信息 |
| `display lldp neighbor-information` | LLDP 邻居信息 |
| `display lldp statistics` | LLDP 统计 |
| `display http_file_cache statistic info` | HTTP 文件缓存统计 |
| `display update-http-proxy` | HTTP 代理更新 |
| `display debugging all` | 调试开关 |
| `display tdma user-net` | TDMA 用户网络 |

### 解析约定
- 配置解析时，`display current-config` 的输出可直接喂给本系统的配置解析器（ConfigParser）。
- 会话/流量类命令（`display ip session`、`display statistics`）的输出可参考其字段结构与日志解析器（LogParser）做配对。
- LLDP 相关命令的输出可作为 TopologyEngine 拓扑发现的依据。
""",
        references=[
            "https://support.huawei.com/hedex/hdx.do?docid=EDOC1100313731&id=ZH-CN_TOPIC_0000001314006092",
        ],
        standard_ref="EDOC1100313731 命令参考 显示类命令",
    ),
    dict(
        title="华为 S12700 交换机查看设备状态命令参考（V200R019C10）",
        category="command_reference",
        vendor="Huawei",
        device_family="S12700/S12700E",
        os_version="V200R019C10",
        mapping_target="config_parser",
        trigger_keywords=[
            "display cpu-usage", "display cpu-usage configuration", "display cpu-usage history",
            "display device", "display device manufacture-info", "display diagnostic-information",
            "display environment version", "display elabel", "display esn", "display fan", "display fan-para",
            "display health", "display memory-usage", "display memory-usage threshold",
            "display package-information", "display power", "display power system",
            "display system-mac", "display transceiver", "display temperature", "display version",
            "display voltage", "display version", "S12700", "S12700E", "华为交换机", "园区核心交换机",
        ],
        summary="华为 S12700/S12700E V200R019C10 全部“查看设备状态的命令”清单，覆盖系统版本、硬件资产、CPU/内存、风扇、电源、温度、电压等设备状态审计场景。来源于华为官方产品文档 EDOC1100126513。",
        content_md="""## 华为 S12700 交换机查看设备状态的命令（V200R019C10）

来源：S12700, S12700E V200R019C10 产品文档（EDOC1100126513）
章节：设备管理命令 → 查看设备状态的命令
原文：<https://support.huawei.com/hedex/hdx.do?docid=EDOC1100126513&id=ZH-CN_CONCEPT_0177113659>

### 系统与版本
| 命令 | 说明 |
|------|------|
| `display version` | 设备软件版本 |
| `display version`（集群） | 集群系统版本 |
| `display system-mac` | 系统 MAC |
| `display esn` | 设备序列号（ESN） |
| `display elabel` | 电子标签 |
| `display device manufacture-info` | 设备制造信息 |
| `display package-information` | 软件包信息 |
| `display diagnostic-information` | 诊断信息（综合） |

### 硬件运行状态
| 命令 | 说明 |
|------|------|
| `display device` | 设备部件信息 |
| `display health` | 设备健康状态 |
| `display fan` | 风扇状态 |
| `display fan-para` | 风扇参数 |
| `display power` | 电源状态 |
| `display power system` | 电源系统 |
| `display temperature` | 温度 |
| `display voltage` | 电压 |
| `display environment version` | 环境监控版本 |
| `display transceiver` | 光模块信息 |

### CPU / 内存
| 命令 | 说明 |
|------|------|
| `display cpu-usage` | CPU 使用率 |
| `display cpu-usage configuration` | CPU 使用率配置 |
| `display cpu-usage history` | CPU 使用率历史 |
| `display memory-usage` | 内存使用率 |
| `display memory-usage threshold` | 内存阈值配置 |

### 解析约定
- `display diagnostic-information` 的输出是综合诊断信息，适合作为整体设备巡检的输入。
- `display transceiver` 输出可用于核查非华为认证光模块（合规风险）。
- `display health` 综合健康度可对接到本系统设备状态审计仪表板。
""",
        references=[
            "https://support.huawei.com/hedex/hdx.do?docid=EDOC1100126513&id=ZH-CN_CONCEPT_0177113659",
        ],
        standard_ref="EDOC1100126513 设备管理命令 查看设备状态的命令",
    ),
]


async def _ensure_seeded(db: AsyncSession):
    """If manuals table is empty, populate SEED_MANUALS so UI has content out of the box."""
    c_stmt = select(func.count()).select_from(Manual)
    if int((await db.execute(c_stmt)).scalar() or 0) > 0:
        return
    for seed in SEED_MANUALS:
        db.add(Manual(
            title=seed["title"],
            category=_enum_or(seed["category"], ManualCategory, ManualCategory.CONFIG_PATTERN),
            vendor=seed.get("vendor"),
            device_family=seed.get("device_family"),
            os_version=seed.get("os_version"),
            mapping_target=_enum_or(seed.get("mapping_target"), MappingTarget),
            trigger_keywords=seed.get("trigger_keywords"),
            signature_patterns=seed.get("signature_patterns"),
            summary=seed.get("summary"),
            content_md=seed["content_md"] or "",
            references=seed.get("references"),
            standard_ref=seed.get("standard_ref"),
        ))
    await db.commit()


@router.get("/dictionaries/manuals", response_model=List[ManualRead])
async def list_dictionary_manuals(
    category: Optional[str] = Query(None),
    mapping_target: Optional[str] = Query(None),
    vendor: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    await _ensure_seeded(db)
    stmt = select(Manual)
    if category:
        stmt = stmt.where(Manual.category == _enum_or(category, ManualCategory, ManualCategory.CONFIG_PATTERN))
    if mapping_target:
        stmt = stmt.where(Manual.mapping_target == _enum_or(mapping_target, MappingTarget))
    if vendor:
        stmt = stmt.where(Manual.vendor == vendor)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(
            Manual.title.ilike(like),
            Manual.summary.ilike(like),
            Manual.content_md.ilike(like),
            cast(Manual.trigger_keywords, String).ilike(like),
        ))
    stmt = stmt.order_by(Manual.updated_at.desc()).limit(limit)
    res = await db.execute(stmt)
    return [_to_read(m) for m in res.scalars().all()]
