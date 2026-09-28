from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_async_session
from app.api.dependencies import get_current_user, get_current_admin, get_current_manager, get_current_project_manager
from app.models.customers import Customer
from app.models.users import User
from app.models.projects import Project
from app.models.user_projects import UserProject
from app.schemas.customers import CreateCustomer, UpdateCustomer, CustomerResponse
from app.crud.customers import customer_crud
from sqlalchemy import select

router = APIRouter(
    prefix="/customer",
    tags=["Customers"],
    responses={404: {"description": "Customer not found"}},
)

@router.get("/", response_model=List[CustomerResponse], summary="List Customers")
async def list_customers(
    skip: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
):
    """
    List all customers.
    """
    role = (user.role or "").lower()
    
    if role in ("admin", "manager"):
        return await customer_crud.get_many(session)
    
    # For project managers or other users, only show customers they are associated with
    # via project assignments
    stmt = (
        select(Customer)
        .join(Project, Project.customer_id == Customer.id)
        .join(UserProject, UserProject.project_id == Project.id)
        .where(UserProject.user_id == user.id)
        .distinct()
    )
    result = await session.execute(stmt)
    return result.scalars().all()

@router.get("/{id}", response_model=CustomerResponse, summary="Get Customer")
async def get_customer(
    id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
):
    """
    Get a customer by ID.
    """
    customer = await customer_crud.get_one(session, Customer.id == id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer

@router.post("/", response_model=CustomerResponse, summary="Create Customer")
async def create_customer(
    customer: CreateCustomer,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_project_manager),
):
    """
    Create a new customer.
    """
    # Check if exists
    existing = await customer_crud.get_one(session, Customer.customer_name == customer.customer_name)
    if existing:
        raise HTTPException(status_code=400, detail="Customer with this name already exists")
    
    return await customer_crud.create(session, customer)

@router.put("/{id}", response_model=CustomerResponse, summary="Update Customer")
async def update_customer(
    id: int,
    customer_update: UpdateCustomer,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_project_manager),
):
    """
    Update a customer.
    """
    db_customer = await customer_crud.get_one(session, Customer.id == id)
    if not db_customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    return await customer_crud.update(session, db_customer, customer_update)


@router.patch("/{id}", response_model=CustomerResponse, summary="Update Customer (Partial)")
async def update_customer_patch(
    id: int,
    customer_update: UpdateCustomer,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_project_manager),
):
    """
    Update a customer (partial update).
    """
    return await update_customer(id, customer_update, session, user)

@router.delete("/{id}", summary="Delete Customer")
async def delete_customer(
    id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_project_manager),
):
    """
    Delete a customer.
    """
    db_customer = await customer_crud.get_one(session, Customer.id == id)
    if not db_customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    # Check for associated projects
    result = await session.execute(select(Project).where(Project.customer_id == id))
    if result.scalars().first():
        raise HTTPException(
            status_code=400, 
            detail="Cannot delete customer with associated projects. Please delete or reassign the projects first."
        )
    
    await customer_crud.delete(session, db_customer)
    return {"message": "Customer deleted successfully"}
