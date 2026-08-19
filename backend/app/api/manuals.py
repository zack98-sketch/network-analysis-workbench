from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.doc_index import DocIndex

router = APIRouter()


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
