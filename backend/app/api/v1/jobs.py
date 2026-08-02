from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.v1.customers import STAFF_ROLES
from app.api.v1.inventory_items import _get_item_or_404
from app.core.dependencies import get_current_user, require_role
from app.db.base import _now
from app.db.session import get_db
from app.models.asset import Asset
from app.models.customer import Customer
from app.models.inventory_item import InventoryItem
from app.models.job import Job, JobStatus
from app.models.job_labor_entry import JobLaborEntry
from app.models.job_part import JobPart
from app.models.user import User, UserRole
from app.schemas.job import JobCreate, JobListResponse, JobRead, JobStatusUpdate, JobUpdate
from app.schemas.job_labor_entry import JobLaborEntryCreate, JobLaborEntryRead
from app.schemas.job_part import JobPartCreate, JobPartRead

router = APIRouter()


def _get_job_or_404(db: Session, current_user: User, job_id: str) -> Job:
    query = db.query(Job).filter(Job.id == job_id, Job.tenant_id == current_user.tenant_id)
    if current_user.role == UserRole.technician:
        query = query.filter(Job.assigned_technician_id == current_user.id)
    job = query.first()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


def _get_technician_or_404(db: Session, tenant_id: str, technician_id: str) -> User:
    technician = (
        db.query(User)
        .filter(
            User.id == technician_id,
            User.tenant_id == tenant_id,
            User.role == UserRole.technician,
        )
        .first()
    )
    if technician is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Technician not found")
    return technician


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
        .filter(
            Asset.id == payload.asset_id,
            Asset.tenant_id == current_user.tenant_id,
            Asset.customer_id == payload.customer_id,
        )
        .first()
    )
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")

    if payload.assigned_technician_id is not None:
        _get_technician_or_404(db, current_user.tenant_id, payload.assigned_technician_id)

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
    job = _get_job_or_404(db, current_user, job_id)
    updates = payload.model_dump(exclude_unset=True)
    if updates.get("assigned_technician_id") is not None:
        _get_technician_or_404(db, current_user.tenant_id, updates["assigned_technician_id"])
    for field, value in updates.items():
        setattr(job, field, value)
    db.commit()
    db.refresh(job)
    return job


_MANUAL_TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
    JobStatus.open: {JobStatus.in_progress, JobStatus.cancelled},
    JobStatus.in_progress: {JobStatus.done, JobStatus.cancelled},
    JobStatus.done: set(),
    JobStatus.invoiced: set(),
    JobStatus.paid: set(),
    JobStatus.cancelled: set(),
}


@router.patch("/jobs/{job_id}/status", response_model=JobRead)
def update_job_status(
    job_id: str,
    payload: JobStatusUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Job:
    if current_user.role not in (*STAFF_ROLES, UserRole.technician):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted for this role")

    job = _get_job_or_404(db, current_user, job_id)

    allowed = _MANUAL_TRANSITIONS.get(job.status, set())
    if payload.status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot transition job from {job.status.value} to {payload.status.value}",
        )

    job.status = payload.status
    if payload.status == JobStatus.in_progress and job.started_at is None:
        job.started_at = _now()
    if payload.status == JobStatus.done:
        job.completed_at = _now()
    db.commit()
    db.refresh(job)
    return job


@router.post(
    "/jobs/{job_id}/labor-entries", response_model=JobLaborEntryRead, status_code=status.HTTP_201_CREATED
)
def create_labor_entry(
    job_id: str,
    payload: JobLaborEntryCreate,
    current_user: Annotated[User, Depends(require_role(*STAFF_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> JobLaborEntry:
    job = _get_job_or_404(db, current_user, job_id)

    _get_technician_or_404(db, current_user.tenant_id, payload.technician_id)

    entry = JobLaborEntry(
        tenant_id=current_user.tenant_id,
        job_id=job_id,
        technician_id=payload.technician_id,
        start_time=payload.start_time,
        end_time=payload.end_time,
        hourly_rate=payload.hourly_rate,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.post("/jobs/{job_id}/parts", response_model=JobPartRead, status_code=status.HTTP_201_CREATED)
def create_job_part(
    job_id: str,
    payload: JobPartCreate,
    current_user: Annotated[User, Depends(require_role(*STAFF_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> JobPart:
    _get_job_or_404(db, current_user, job_id)
    _get_item_or_404(db, current_user.tenant_id, payload.inventory_item_id)

    # Re-read under a row lock so concurrent decrements serialize on MySQL.
    # SQLite ignores FOR UPDATE, which is harmless for the test suite.
    item = (
        db.query(InventoryItem)
        .filter(
            InventoryItem.id == payload.inventory_item_id,
            InventoryItem.tenant_id == current_user.tenant_id,
        )
        .with_for_update()
        .one()
    )

    available = item.quantity_on_hand
    shortfall = max(0.0, payload.quantity - available)
    item.quantity_on_hand = max(0.0, available - payload.quantity)

    part = JobPart(
        tenant_id=current_user.tenant_id,
        job_id=job_id,
        inventory_item_id=item.id,
        quantity=payload.quantity,
        unit_cost_at_time=item.unit_cost,
        unit_price_at_time=item.unit_price,
        overdrawn=shortfall > 0,
        shortfall=shortfall,
    )
    db.add(part)
    db.commit()
    db.refresh(part)
    return part
