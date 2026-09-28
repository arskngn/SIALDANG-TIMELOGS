from app.crud.base import CRUDRepository
from app.models.task_types import TaskType


task_type_crud = CRUDRepository(TaskType)