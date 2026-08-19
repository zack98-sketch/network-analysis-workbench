import asyncio
import hashlib
import logging
import traceback
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Header, status
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.material import Material, ParseStatus
from app.models.log_event import LogEvent
from app.models.config_item import ConfigItem
from app.models.doc_index import DocIndex
from app.models.risk_finding import RiskFinding
from app.models.topology import TopoNode, TopoEdge

from app.services.parse_service import ParseService

logger = logging.getLogger("workbench.materials")

router = APIRouter()
_parse_service = ParseService()


class MaterialRead(BaseModel):
    id: int
    project_id: int
    file_name: str
    file_hash: Optional[str] = None
    file_path: str
    file_size: Optional[int] = None
    file_type: Optional[str] = None
    parser_type: Optional[str] = None
    parse_status: str = "pending"
    device_name: Optional[str] = None
    vendor: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# Alias response used by smoke-test frontend-compatible view
class MaterialCompatRead(BaseModel):
    id: int
    name: str
    type: Optional[str] = None
    format: Optional[str] = None
    size: Optional[int] = None
    status: str = "pending"


def _to_read(m: Material) -> MaterialRead:
    return MaterialRead(
        id=m.id,
        project_id=m.project_id,
        file_name=m.file_name,
        file_hash=m.file_hash,
        file_path=m.file_path,
        file_size=m.file_size,
        file_type=m.file_type,
        parser_type=m.parser_type,
        parse_status=m.parse_status.value if hasattr(m.parse_status, "value") else str(m.parse_status),
        device_name=m.device_name,
        vendor=m.vendor,
        created_at=m.created_at,
    )


def _to_compat(m: Material) -> MaterialCompatRead:
    status_str = m.parse_status.value if hasattr(m.parse_status, "value") else str(m.parse_status)
    return MaterialCompatRead(
        id=m.id,
        name=m.file_name,
        type=m.file_type,
        format=m.parser_type,
        size=m.file_size,
        status=status_str,
    )


async def _run_parse_in_background(material_id: int):
    try:
        from app.database import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            try:
                await _parse_service.parse_material(material_id, session)
                await session.commit()
                logger.info("Material %s parsed successfully", material_id)
            except Exception as exc:
                await session.rollback()
                logger.error(
                    "Material %s parse failed: %s\n%s",
                    material_id, exc, traceback.format_exc()
                )
    except Exception as exc:
        logger.error("Background parse task crashed for material %s: %s", material_id, exc)


@router.post("/materials/upload", response_model=MaterialRead, status_code=status.HTTP_201_CREATED)
async def upload_material(
    project_id: int = Form(...),
    file: UploadFile = File(...),
    parser_type: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    raw = await file.read()
    file_hash = hashlib.sha256(raw).hexdigest()

    upload_dir = settings.UPLOAD_DIR / str(project_id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    ext = ""
    fn = file.filename or "uploaded.bin"
    if "." in fn:
        ext = "." + fn.rsplit(".", 1)[-1]
    stored_name = f"{file_hash[:16]}_{fn}"
    target_path = upload_dir / stored_name

    if not target_path.exists():
        with open(target_path, "wb") as f:
            f.write(raw)

    existing_stmt = select(Material).where(
        Material.project_id == project_id,
        Material.file_hash == file_hash,
    )
    existing_res = await db.execute(existing_stmt)
    existing = existing_res.scalar_one_or_none()
    if existing is not None:
        return _to_read(existing)

    material = Material(
        project_id=project_id,
        file_name=fn,
        file_hash=file_hash,
        file_path=str(target_path),
        file_size=len(raw),
        parser_type=parser_type,
        parse_status=ParseStatus.PENDING,
    )
    db.add(material)
    await db.flush()
    await db.refresh(material)
    await db.commit()
    await db.refresh(material)

    asyncio.create_task(_run_parse_in_background(material.id))

    return _to_read(material)


@router.get("/projects/{project_id}/materials", response_model=list[MaterialRead])
async def list_project_materials(project_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(Material).where(Material.project_id == project_id).order_by(Material.created_at.desc())
    res = await db.execute(stmt)
    return [_to_read(m) for m in res.scalars().all()]


@router.get("/materials/{material_id}", response_model=MaterialRead)
async def get_material(material_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(Material).where(Material.id == material_id)
    res = await db.execute(stmt)
    m = res.scalar_one_or_none()
    if m is None:
        raise HTTPException(status_code=404, detail="Material not found")
    return _to_read(m)


@router.delete("/materials/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_material(material_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(Material).where(Material.id == material_id)
    res = await db.execute(stmt)
    m = res.scalar_one_or_none()
    if m is None:
        raise HTTPException(status_code=404, detail="Material not found")

    await db.execute(delete(LogEvent).where(LogEvent.material_id == material_id))
    await db.execute(delete(ConfigItem).where(ConfigItem.material_id == material_id))
    await db.execute(delete(DocIndex).where(DocIndex.material_id == material_id))
    await db.execute(delete(RiskFinding).where(RiskFinding.material_id == material_id))

    project_id = m.project_id
    try:
        import os as _os
        if m.file_path and _os.path.exists(m.file_path):
            _os.remove(m.file_path)
    except Exception:
        pass

    await db.delete(m)
    await db.commit()

    stmt2 = select(Material.id).where(Material.project_id == project_id)
    res2 = await db.execute(stmt2)
    if not res2.scalars().all():
        await db.execute(delete(TopoNode).where(TopoNode.project_id == project_id))
        await db.execute(delete(TopoEdge).where(TopoEdge.project_id == project_id))
        await db.execute(delete(RiskFinding).where(RiskFinding.project_id == project_id))
        await db.commit()

    return None


# --- Compatibility aliases -------------------------------------------------

@router.post("/materials", response_model=MaterialCompatRead, status_code=status.HTTP_201_CREATED)
async def upload_material_alias(
    file: UploadFile = File(...),
    x_project_id: Optional[int] = Header(None, alias="X-Project-Id"),
    project_id: Optional[int] = Form(None),
    parser_type: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """Alias of /materials/upload that accepts X-Project-Id header and returns compat fields."""
    pid = project_id or x_project_id
    if not pid:
        raise HTTPException(status_code=400, detail="project_id is required (form or X-Project-Id header)")
    raw = await file.read()
    file_hash = hashlib.sha256(raw).hexdigest()

    upload_dir = settings.UPLOAD_DIR / str(pid)
    upload_dir.mkdir(parents=True, exist_ok=True)

    fn = file.filename or "uploaded.bin"
    ext = ""
    if "." in fn:
        ext = "." + fn.rsplit(".", 1)[-1]
    stored_name = f"{file_hash[:16]}_{fn}"
    target_path = upload_dir / stored_name

    if not target_path.exists():
        with open(target_path, "wb") as f:
            f.write(raw)

    existing_stmt = select(Material).where(
        Material.project_id == pid,
        Material.file_hash == file_hash,
    )
    existing_res = await db.execute(existing_stmt)
    existing = existing_res.scalar_one_or_none()
    if existing is not None:
        return _to_compat(existing)

    material = Material(
        project_id=pid,
        file_name=fn,
        file_hash=file_hash,
        file_path=str(target_path),
        file_size=len(raw),
        parser_type=parser_type,
        parse_status=ParseStatus.PENDING,
    )
    db.add(material)
    await db.flush()
    await db.refresh(material)
    await db.commit()
    await db.refresh(material)

    asyncio.create_task(_run_parse_in_background(material.id))

    return _to_compat(material)


@router.get("/materials/{material_id}/config/tree")
async def get_material_config_tree_flat(
    material_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Flat config/tree endpoint: returns list of sections (smoke-test compatible)."""
    stmt = (
        select(ConfigItem)
        .where(ConfigItem.material_id == material_id)
        .order_by(ConfigItem.line_no.asc().nullslast(), ConfigItem.id.asc())
    )
    res = await db.execute(stmt)
    cis = list(res.scalars().all())

    sections_map = {}
    for ci in cis:
        key = (ci.section_type or "root", ci.section_name or "")
        if key not in sections_map:
            sections_map[key] = {
                "section_type": key[0],
                "section_name": key[1] or None,
                "device_name": ci.device_name,
                "items": [],
            }
        sections_map[key]["items"].append({
            "id": ci.id,
            "line_no": ci.line_no,
            "raw_line": ci.raw_line,
            "key": ci.key,
            "value": ci.value,
            "indent_level": ci.indent_level or 0,
            "annotation": ci.annotation,
            "doc_ref": ci.doc_ref,
            "is_risk": bool(ci.is_risk),
            "risk_level": ci.risk_level.value if ci.risk_level and hasattr(ci.risk_level, "value") else str(ci.risk_level or "none"),
        })
    return list(sections_map.values())


@router.post("/materials/{material_id}/reparse", response_model=MaterialRead)
async def reparse_material(material_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(Material).where(Material.id == material_id)
    res = await db.execute(stmt)
    m = res.scalar_one_or_none()
    if m is None:
        raise HTTPException(status_code=404, detail="Material not found")

    asyncio.create_task(_run_parse_in_background(material_id))

    stmt2 = select(Material).where(Material.id == material_id)
    res2 = await db.execute(stmt2)
    updated = res2.scalar_one()
    return _to_read(updated)
