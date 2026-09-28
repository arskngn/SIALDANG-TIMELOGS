from datetime import datetime
from sqlalchemy import Column, Integer, String
from app.database import Base


class Role(Base):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True, autoincrement=True)
    role_name = Column(String(50), nullable=False, unique=True)

DEFAULT_ROLES = (
    "admin",
    "manager",
    "user",
)
