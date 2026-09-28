from app.crud.base import CRUDRepository
from app.models.user_projects import UserProject

user_project_crud = CRUDRepository(UserProject)