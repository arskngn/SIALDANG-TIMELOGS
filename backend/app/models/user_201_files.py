from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum, Boolean
from app.database import Base


class User201File(Base):
    __tablename__ = "user_201_files"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    file_name = Column(String(255), nullable=False)
    document_type_id = Column(Integer, ForeignKey("document_types.id"), nullable=False)
    file_url = Column(String(500), nullable=True)
    s3_path = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)
    remarks = Column(Text, nullable=True)
    status = Column(Enum("Pending", "Approved", "Declined", name="user201_status"), nullable=False, default="Pending")
    approver_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    version = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now)
