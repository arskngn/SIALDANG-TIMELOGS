from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_async_session
from app.api.dependencies import get_current_admin, get_current_user
from app.models.document_types import DocumentType
from app.schemas.document_types import CreateDocumentType, UpdateDocumentType, DocumentTypeResponse
from app.crud.document_types import document_type_crud
from sqlalchemy import select


router = APIRouter(
    prefix="/document-type",
    tags=["DocumentTypes"],
    responses={404: {"description": "Document type not found"}},
)


@router.get("/", response_model=List[DocumentTypeResponse])
async def list_document_types(session: AsyncSession = Depends(get_async_session), user: DocumentType = Depends(get_current_admin)):
    items = await document_type_crud.get_many(session)
    return [DocumentTypeResponse.model_validate(i, from_attributes=True) for i in items]


@router.get("/all", response_model=List[DocumentTypeResponse])
async def list_document_types_public(session: AsyncSession = Depends(get_async_session), user: DocumentType = Depends(get_current_user)):
    items = await document_type_crud.get_many(session)
    return [DocumentTypeResponse.model_validate(i, from_attributes=True) for i in items]


@router.post("/", response_model=DocumentTypeResponse)
async def create_document_type(payload: CreateDocumentType, session: AsyncSession = Depends(get_async_session), user: DocumentType = Depends(get_current_admin)):
    created = await document_type_crud.create(session, payload)
    return DocumentTypeResponse.model_validate(created, from_attributes=True)


@router.get("/{doc_type_id}", response_model=DocumentTypeResponse)
async def get_document_type(doc_type_id: int, session: AsyncSession = Depends(get_async_session), user: DocumentType = Depends(get_current_admin)):
    item = await document_type_crud.get_one(session, DocumentType.id == doc_type_id)
    if not item:
        raise HTTPException(status_code=404, detail="Document type not found")
    return DocumentTypeResponse.model_validate(item, from_attributes=True)


@router.patch("/{doc_type_id}", response_model=DocumentTypeResponse)
async def update_document_type(doc_type_id: int, payload: UpdateDocumentType, session: AsyncSession = Depends(get_async_session), user: DocumentType = Depends(get_current_admin)):
    item = await document_type_crud.get_one(session, DocumentType.id == doc_type_id)
    if not item:
        raise HTTPException(status_code=404, detail="Document type not found")
    updated = await document_type_crud.update(session, item, payload)
    return DocumentTypeResponse.model_validate(updated, from_attributes=True)


@router.delete("/{doc_type_id}", status_code=status.HTTP_200_OK)
async def delete_document_type(doc_type_id: int, session: AsyncSession = Depends(get_async_session), user: DocumentType = Depends(get_current_admin)):
    item = await document_type_crud.get_one(session, DocumentType.id == doc_type_id)
    if not item:
        raise HTTPException(status_code=404, detail="Document type not found")
    await document_type_crud.delete(session, item)
    return {"message": "Document type successfully deleted"}
