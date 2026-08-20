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
