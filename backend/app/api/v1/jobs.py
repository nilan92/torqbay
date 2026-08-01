from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.v1.customers import STAFF_ROLES
from app.core.dependencies import get_current_user, require_role
from app.db.session import get_db
from app.models.asset import Asset
from app.models.customer import Customer
from app.models.job import Job
from app.models.user import User, UserRole
from app.schemas.job import JobCreate, JobListResponse, JobRead, JobUpdate

router = APIRouter()


def _get_job_or_404(db: Session, current_user: User, job_id: str) -> Job:
    query = db.query(Job).filter(Job.id == job_id, Job.tenant_id == current_user.tenant_id)
    if current_user.role == UserRole.technician:
        query = query.filter(Job.assigned_technician_id == current_user.id)
    job = query.first()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.post("/jobs", response_model=JobRead, status_code=status.HTTP_201_CREATED)
def create_job(
    payload: JobCreate,
    current_user: Annotated[User, Depends(require_role(*STAFF_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> Job:
    customer = (
        db.query(Customer)
        .filter(Customer.id == payload.customer_id, Customer.tenant_id == current_user.tenant_id)
        .first()
    )
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

    asset = (
        db.query(Asset)
        .filter(Asset.id == payload.asset_id, Asset.tenant_id == current_user.tenant_id)
        .first()
    )
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")

    job = Job(
        tenant_id=current_user.tenant_id,
        customer_id=payload.customer_id,
        asset_id=payload.asset_id,
        title=payload.title,
        description=payload.description,
        assigned_technician_id=payload.assigned_technician_id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.get("/jobs", response_model=JobListResponse)
def list_jobs(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> JobListResponse:
    query = db.query(Job).filter(Job.tenant_id == current_user.tenant_id)
    if current_user.role == UserRole.technician:
        query = query.filter(Job.assigned_technician_id == current_user.id)
    total = query.count()
    jobs = query.offset((page - 1) * page_size).limit(page_size).all()
    return JobListResponse(items=jobs, total=total, page=page, page_size=page_size)


@router.get("/jobs/{job_id}", response_model=JobRead)
def get_job(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Job:
    return _get_job_or_404(db, current_user, job_id)


@router.patch("/jobs/{job_id}", response_model=JobRead)
def update_job(
    job_id: str,
    payload: JobUpdate,
    current_user: Annotated[User, Depends(require_role(*STAFF_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> Job:
    job = (
        db.query(Job)
        .filter(Job.id == job_id, Job.tenant_id == current_user.tenant_id)
        .first()
    )
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(job, field, value)
    db.commit()
    db.refresh(job)
    return job
