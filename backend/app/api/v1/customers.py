from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_role
from app.db.session import get_db
from app.models.customer import Customer
from app.models.user import User, UserRole
from app.schemas.customer import CustomerCreate, CustomerListResponse, CustomerRead, CustomerUpdate

router = APIRouter()

STAFF_ROLES = (UserRole.owner, UserRole.manager, UserRole.frontdesk)


def _get_customer_or_404(db: Session, tenant_id: str, customer_id: str) -> Customer:
    customer = (
        db.query(Customer)
        .filter(Customer.id == customer_id, Customer.tenant_id == tenant_id)
        .first()
    )
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return customer


@router.post("/customers", response_model=CustomerRead, status_code=status.HTTP_201_CREATED)
def create_customer(
    payload: CustomerCreate,
    current_user: Annotated[User, Depends(require_role(*STAFF_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> Customer:
    customer = Customer(tenant_id=current_user.tenant_id, **payload.model_dump())
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


@router.get("/customers", response_model=CustomerListResponse)
def list_customers(
    current_user: Annotated[User, Depends(require_role(*STAFF_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> CustomerListResponse:
    query = db.query(Customer).filter(Customer.tenant_id == current_user.tenant_id)
    total = query.count()
    customers = query.offset((page - 1) * page_size).limit(page_size).all()
    return CustomerListResponse(items=customers, total=total, page=page, page_size=page_size)


@router.get("/customers/{customer_id}", response_model=CustomerRead)
def get_customer(
    customer_id: str,
    current_user: Annotated[User, Depends(require_role(*STAFF_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> Customer:
    return _get_customer_or_404(db, current_user.tenant_id, customer_id)


@router.patch("/customers/{customer_id}", response_model=CustomerRead)
def update_customer(
    customer_id: str,
    payload: CustomerUpdate,
    current_user: Annotated[User, Depends(require_role(*STAFF_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> Customer:
    customer = _get_customer_or_404(db, current_user.tenant_id, customer_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(customer, field, value)
    db.commit()
    db.refresh(customer)
    return customer
