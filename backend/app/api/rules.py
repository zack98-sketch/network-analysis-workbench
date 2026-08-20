from datetime import datetime
from typing import Optional
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.config import settings

router = APIRouter()


class RuleBase(BaseModel):
    name: str
    rule_type: str = "custom"
    severity: str = "warning"
    enabled: bool = True
    yaml_content: Optional[str] = None


class RuleCreate(RuleBase):
    pass


class RuleUpdate(BaseModel):
    name: Optional[str] = None
    rule_type: Optional[str] = None
    severity: Optional[str] = None
    enabled: Optional[bool] = None
    yaml_content: Optional[str] = None


class RuleRead(RuleBase):
    id: int
    created_at: datetime
    domain: Optional[str] = None

    class Config:
        from_attributes = True


class RuleTemplate(BaseModel):
    key: str
    name: str
    rule_type: str
    severity: str
    description: str
    yaml_content: str


def _load_yaml_rules() -> list[dict]:
    """Scan built-in YAML rule files and produce flattened rule list."""
    rules_dir = settings.BASE_DIR / "app" / "rules"
    if not rules_dir.exists():
        return []
    try:
        import yaml
    except ImportError:
        yaml = None

    rules: list[dict] = []
    rid = 1
    for fname in sorted(rules_dir.glob("*.yaml")):
        domain = fname.stem
        try:
            text = fname.read_text(encoding="utf-8")
        except Exception:
            continue
        if yaml is None:
            # fallback: simple heuristics
            rules.append({
                "id": rid,
                "name": f"{domain} 规则库",
                "rule_type": "config",
                "severity": "medium",
                "enabled": True,
                "yaml_content": text,
                "domain": domain,
                "created_at": datetime.utcnow(),
            })
            rid += 1
            continue
        try:
            data = yaml.safe_load(text)
        except Exception:
            continue
        if isinstance(data, dict) and "rules" in data and isinstance(data["rules"], list):
            for r in data["rules"]:
                if not isinstance(r, dict):
                    continue
                rules.append({
                    "id": rid,
                    "name": r.get("name") or r.get("id") or f"{domain}-{rid}",
                    "rule_type": r.get("category") or domain,
                    "severity": (r.get("severity") or "medium").lower(),
                    "enabled": True,
                    "yaml_content": text,
                    "domain": r.get("category") or domain,
                    "description": r.get("description") or "",
                    "created_at": datetime.utcnow(),
                })
                rid += 1
        elif isinstance(data, list):
            for r in data:
                if not isinstance(r, dict):
                    continue
                rules.append({
                    "id": rid,
                    "name": r.get("name") or r.get("id") or f"{domain}-{rid}",
                    "rule_type": r.get("rule_type") or domain,
                    "severity": (r.get("severity") or "medium").lower(),
                    "enabled": True,
                    "yaml_content": text,
                    "domain": r.get("domain") or domain,
                    "description": r.get("description") or "",
                    "created_at": datetime.utcnow(),
                })
                rid += 1
        else:
            # single rule file without list
            rules.append({
                "id": rid,
                "name": (data or {}).get("name") if isinstance(data, dict) else f"{domain} 规则库",
                "rule_type": domain,
                "severity": "medium",
                "enabled": True,
                "yaml_content": text,
                "domain": domain,
                "created_at": datetime.utcnow(),
            })
            rid += 1
    return rules


_cached_rules: Optional[list] = None


def _get_cached_rules() -> list[dict]:
    global _cached_rules
    if _cached_rules is None:
        _cached_rules = _load_yaml_rules()
    return _cached_rules


def _to_rule_read(d: dict) -> RuleRead:
    return RuleRead(
        id=int(d.get("id", 0)),
        name=d.get("name", ""),
        rule_type=d.get("rule_type", "custom"),
        severity=d.get("severity", "warning"),
        enabled=bool(d.get("enabled", True)),
        yaml_content=d.get("yaml_content"),
        domain=d.get("domain"),
        created_at=d.get("created_at") or datetime.utcnow(),
    )


@router.get("/rules", response_model=list[RuleRead])
async def list_rules(
    rule_type: Optional[str] = None,
    enabled_only: bool = False,
    db: AsyncSession = Depends(get_db),
):
    all_rules = _get_cached_rules()
    out = []
    for r in all_rules:
        if enabled_only and not r.get("enabled", True):
            continue
        if rule_type:
            rt = (r.get("rule_type") or "").lower()
            dom = (r.get("domain") or "").lower()
            q = rule_type.lower()
            if q not in rt and q not in dom:
                continue
        out.append(_to_rule_read(r))
    return out


@router.post("/rules", response_model=RuleRead, status_code=status.HTTP_201_CREATED)
async def create_rule(payload: RuleCreate, db: AsyncSession = Depends(get_db)):
    all_rules = _get_cached_rules()
    new_id = max((r.get("id", 0) for r in all_rules), default=0) + 1
    r = {
        "id": new_id,
        "name": payload.name,
        "rule_type": payload.rule_type,
        "severity": payload.severity,
        "enabled": payload.enabled,
        "yaml_content": payload.yaml_content,
        "domain": payload.rule_type,
        "created_at": datetime.utcnow(),
    }
    all_rules.append(r)
    return _to_rule_read(r)


@router.get("/rules/{rule_id}", response_model=RuleRead)
async def get_rule(rule_id: int, db: AsyncSession = Depends(get_db)):
    for r in _get_cached_rules():
        if int(r.get("id", 0)) == rule_id:
            return _to_rule_read(r)
    raise HTTPException(status_code=404, detail="Rule not found")


@router.put("/rules/{rule_id}", response_model=RuleRead)
async def update_rule(rule_id: int, payload: RuleUpdate, db: AsyncSession = Depends(get_db)):
    for r in _get_cached_rules():
        if int(r.get("id", 0)) == rule_id:
            if payload.name is not None:
                r["name"] = payload.name
            if payload.rule_type is not None:
                r["rule_type"] = payload.rule_type
                r["domain"] = payload.rule_type
            if payload.severity is not None:
                r["severity"] = payload.severity
            if payload.enabled is not None:
                r["enabled"] = payload.enabled
            if payload.yaml_content is not None:
                r["yaml_content"] = payload.yaml_content
            return _to_rule_read(r)
    raise HTTPException(status_code=404, detail="Rule not found")


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(rule_id: int, db: AsyncSession = Depends(get_db)):
    all_rules = _get_cached_rules()
    for i, r in enumerate(all_rules):
        if int(r.get("id", 0)) == rule_id:
            del all_rules[i]
            return None
    raise HTTPException(status_code=404, detail="Rule not found")


@router.get("/rules/templates", response_model=list[RuleTemplate])
async def list_rule_templates(db: AsyncSession = Depends(get_db)):
    return [
        RuleTemplate(
            key="password-no-encrypt",
            name="未加密密码检测",
            rule_type="config",
            severity="high",
            description="检测明文密码配置",
            yaml_content="match: 'password\\s+\\S+'\nexcept: 'password\\s+.*(encrypted|7\\s|5\\s).*'\n",
        ),
        RuleTemplate(
            key="ssh-weak-cipher",
            name="SSH 弱加密算法",
            rule_type="config",
            severity="medium",
            description="检测 SSH 使用不安全的加密算法",
            yaml_content="match: 'ssh.*cipher.*(3des|des|blowfish)'\n",
        ),
        RuleTemplate(
            key="login-failed-threshold",
            name="登录失败阈值",
            rule_type="log",
            severity="warning",
            description="登录失败次数超过阈值",
            yaml_content="pattern: 'Login\\s+failed'\nthreshold: 5\nwindow: '5m'\n",
        ),
    ]
