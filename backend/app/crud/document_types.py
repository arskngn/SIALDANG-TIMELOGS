from app.crud.base import CRUDRepository
from app.models.document_types import DocumentType


document_type_crud = CRUDRepository(DocumentType)
