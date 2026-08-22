from typing import Optional, Dict, List, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.config_item import ConfigItem
from app.models.material import Material

router = APIRouter()


class ConfigItemRead(BaseModel):
    id: int
    material_id: int
    device_name: Optional[str] = None
    section_type: Optional[str] = None
    section_name: Optional[str] = None
    line_no: Optional[int] = None
    raw_line: Optional[str] = None
    key: Optional[str] = None
    value: Optional[str] = None
    indent_level: int = 0
    annotation: Optional[str] = None
    doc_ref: Optional[str] = None
    is_risk: bool = False
    risk_level: str = "none"

    class Config:
        from_attributes = True


class ConfigSection(BaseModel):
    section_type: str
    section_name: Optional[str] = None
    items: list[ConfigItemRead]


class ConfigTreeResponse(BaseModel):
    material_id: int
    device_name: Optional[str] = None
    sections: list[ConfigSection]


class ConfigDiffEntry(BaseModel):
    line_no_a: Optional[int]
    line_no_b: Optional[int]
    op: str
    text_a: Optional[str]
    text_b: Optional[str]


class ConfigDiffResponse(BaseModel):
    base_material_id: int
    compare_material_id: int
    diff: list[ConfigDiffEntry]
    added: int
    removed: int
    changed: int


def _ci_to_read(ci: ConfigItem) -> ConfigItemRead:
    return ConfigItemRead(
        id=ci.id,
        material_id=ci.material_id,
        device_name=ci.device_name,
        section_type=ci.section_type,
        section_name=ci.section_name,
        line_no=ci.line_no,
        raw_line=ci.raw_line,
        key=ci.key,
        value=ci.value,
        indent_level=ci.indent_level or 0,
        annotation=ci.annotation,
        doc_ref=ci.doc_ref,
        is_risk=bool(ci.is_risk),
        risk_level=ci.risk_level.value if ci.risk_level and hasattr(ci.risk_level, "value") else str(ci.risk_level or "none"),
    )


@router.get("/materials/{material_id}/config-tree", response_model=ConfigTreeResponse)
@router.get("/materials/{material_id}/config/tree", response_model=ConfigTreeResponse)
async def get_config_tree(
    material_id: int,
    section_type: Optional[str] = Query(None),
    only_risks: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    where_clauses = [ConfigItem.material_id == material_id]
    if section_type:
        where_clauses.append(ConfigItem.section_type == section_type)
    if only_risks:
        where_clauses.append(ConfigItem.is_risk == True)

    stmt = (
        select(ConfigItem)
        .where(and_(*where_clauses))
        .order_by(ConfigItem.line_no.asc().nullslast(), ConfigItem.id.asc())
    )
    res = await db.execute(stmt)
    items = list(res.scalars().all())

    device_name = None
    for it in items:
        if it.device_name:
            device_name = it.device_name
            break

    sections_map: Dict[tuple, List[ConfigItemRead]] = {}
    for ci in items:
        key = (ci.section_type or "__root__", ci.section_name or "")
        sections_map.setdefault(key, []).append(_ci_to_read(ci))

    sections = []
    for (st, sn), items_list in sections_map.items():
        sections.append(ConfigSection(
            section_type=st if st != "__root__" else "root",
            section_name=sn or None,
            items=items_list,
        ))

    return ConfigTreeResponse(
        material_id=material_id,
        device_name=device_name,
        sections=sections,
    )


@router.get("/materials/{material_id}/diff", response_model=ConfigDiffResponse)
@router.get("/materials/{material_id}/config/diff", response_model=ConfigDiffResponse)
async def get_config_diff(
    material_id: int,
    compare_with: int = Query(..., alias="compare_with"),
    context: int = Query(3, ge=0, le=10),
    db: AsyncSession = Depends(get_db),
):
    stmt_a = (
        select(ConfigItem)
        .where(ConfigItem.material_id == material_id)
        .order_by(ConfigItem.line_no.asc().nullslast(), ConfigItem.id.asc())
    )
    res_a = await db.execute(stmt_a)
    items_a = list(res_a.scalars().all())
    lines_a = [
        (ci.line_no or 0, ci.raw_line or (ci.key or "") + " " + (ci.value or ""))
        for ci in items_a
    ]

    stmt_b = (
        select(ConfigItem)
        .where(ConfigItem.material_id == compare_with)
        .order_by(ConfigItem.line_no.asc().nullslast(), ConfigItem.id.asc())
    )
    res_b = await db.execute(stmt_b)
    items_b = list(res_b.scalars().all())
    lines_b = [
        (ci.line_no or 0, ci.raw_line or (ci.key or "") + " " + (ci.value or ""))
        for ci in items_b
    ]

    text_a_list = [ln.strip() for _, ln in lines_a]
    text_b_list = [ln.strip() for _, ln in lines_b]

    try:
        import difflib
        sm = difflib.SequenceMatcher(a=text_a_list, b=text_b_list)
        diff: List[ConfigDiffEntry] = []
        added = removed = changed = 0
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                continue
            if tag == "replace":
                n = max(i2 - i1, j2 - j1)
                for k in range(n):
                    ai = i1 + k if (i1 + k) < i2 else None
                    bj = j1 + k if (j1 + k) < j2 else None
                    la = lines_a[ai][1].strip() if ai is not None else None
                    lb = lines_b[bj][1].strip() if bj is not None else None
                    ln_a = lines_a[ai][0] if ai is not None else None
                    ln_b = lines_b[bj][0] if bj is not None else None
                    sub = "changed"
                    if la is None:
                        sub = "added"
                        added += 1
                    elif lb is None:
                        sub = "removed"
                        removed += 1
                    else:
                        changed += 1
                    diff.append(ConfigDiffEntry(
                        line_no_a=ln_a, line_no_b=ln_b,
                        op=sub, text_a=la, text_b=lb,
                    ))
            elif tag == "delete":
                for ai in range(i1, i2):
                    ln_a, la = lines_a[ai]
                    diff.append(ConfigDiffEntry(
                        line_no_a=ln_a, line_no_b=None,
                        op="removed", text_a=la.strip(), text_b=None,
                    ))
                    removed += 1
            elif tag == "insert":
                for bj in range(j1, j2):
                    ln_b, lb = lines_b[bj]
                    diff.append(ConfigDiffEntry(
                        line_no_a=None, line_no_b=ln_b,
                        op="added", text_a=None, text_b=lb.strip(),
                    ))
                    added += 1
    except Exception:
        diff = []
        added = removed = changed = 0

    return ConfigDiffResponse(
        base_material_id=material_id,
        compare_material_id=compare_with,
        diff=diff,
        added=added,
        removed=removed,
        changed=changed,
    )
