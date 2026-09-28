from datetime import datetime
from sqlalchemy import Column, Integer, String, Enum, Boolean, DateTime
from app.database import Base


class DocumentType(Base):
    __tablename__ = "document_types"
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(50), nullable=False, unique=True)
    name = Column(String(150), nullable=False)
    category = Column(Enum("pre-employment", "payroll", "government", name="document_type_category"), nullable=False)
    required = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
