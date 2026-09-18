from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models import Allocation, Designation, Employee, EmployeeStatus
from app.schemas import EmployeeIn, EmployeeOut, EmployeeUpdate
from app.services.allocation_service import employee_workload

router = APIRouter(prefix="/employees", tags=["employees"])


@router.get("", response_model=list[EmployeeOut])
def list_employees(
    db: Session = Depends(get_db),
    designation_id: int | None = None,
    stage_id: int | None = None,
    employee_status: EmployeeStatus | None = None,
    search: str | None = None,
    limit: int = Query(500, le=5000),
    offset: int = 0,
):
    stmt = select(Employee).options(selectinload(Employee.designation))
    if designation_id:
        stmt = stmt.where(Employee.designation_id == designation_id)
    if employee_status:
        stmt = stmt.where(Employee.status == employee_status)
    if search:
        pattern = f"%{search.lower()}%"
        stmt = stmt.where(
            func.lower(Employee.name).like(pattern) | func.lower(Employee.employee_code).like(pattern)
        )
    if stage_id:
        from app.models import StageDesignation

        stmt = stmt.join(
            StageDesignation, StageDesignation.designation_id == Employee.designation_id
        ).where(StageDesignation.stage_id == stage_id)
    return db.scalars(stmt.order_by(Employee.employee_code).limit(limit).offset(offset)).all()


@router.post("", response_model=EmployeeOut, status_code=status.HTTP_201_CREATED)
def create_employee(payload: EmployeeIn, db: Session = Depends(get_db)):
    if not db.get(Designation, payload.designation_id):
        raise HTTPException(404, "Designation not found")
    employee = Employee(**payload.model_dump())
    db.add(employee)
    try:
        db.flush()
    except IntegrityError as exc:
        raise HTTPException(409, f"Employee code {payload.employee_code} already exists") from exc
    db.refresh(employee)
    return employee


@router.get("/{employee_id}", response_model=EmployeeOut)
def get_employee(employee_id: int, db: Session = Depends(get_db)):
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(404, "Employee not found")
    return employee


@router.patch("/{employee_id}", response_model=EmployeeOut)
def update_employee(employee_id: int, payload: EmployeeUpdate, db: Session = Depends(get_db)):
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(404, "Employee not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(employee, field, value)
    db.flush()
    return employee


@router.delete("/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_employee(employee_id: int, db: Session = Depends(get_db)):
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(404, "Employee not found")
    booked = db.scalar(
        select(func.count()).select_from(Allocation).where(Allocation.employee_id == employee_id)
    )
    if booked:
        raise HTTPException(
            409,
            f"{employee.employee_code} has {booked} allocation(s). Set status to Inactive instead "
            "so historical plans stay intact.",
        )
    db.delete(employee)


@router.get("/{employee_id}/workload")
def get_workload(employee_id: int, db: Session = Depends(get_db)):
    if not db.get(Employee, employee_id):
        raise HTTPException(404, "Employee not found")
    rows = employee_workload(db, employee_id)
    return {
        "employee_id": employee_id,
        "allocations": rows,
        "total_allocated_days": sum((r["end"] - r["start"]).days + 1 for r in rows),
    }
