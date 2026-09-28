from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from app.database import Base


class UserProject(Base):
    __tablename__ = "user_projects"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    assigned_at = Column(DateTime, nullable=False, default=datetime.now)
    role_in_project = Column(String(100), nullable=True)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=True)
    fte = Column(Integer,nullable=False)
