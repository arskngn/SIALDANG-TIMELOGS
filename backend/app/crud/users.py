from app.crud.base import CRUDRepository
from app.models.users import User


class UserCRUD(CRUDRepository):
    pass


user_crud = UserCRUD(model=User)
