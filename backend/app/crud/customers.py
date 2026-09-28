from app.crud.base import CRUDRepository
from app.models.customers import Customer

class CRUDCustomer(CRUDRepository[Customer]):
    pass

customer_crud = CRUDCustomer(Customer)
