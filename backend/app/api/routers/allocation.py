from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Allocation, Project, ProjectStage, Shortage, Task
from app.schemas import AllocationOut, AllocationRunOut, ConflictOut, ShortageOut
from app.services.allocation_service import find_conflicts, run_allocation
from app.services.scheduling_service import SchedulingError

router = APIRouter(tags=["allocation"])


@router.post("/projects/{project_id}/allocate", response_model=AllocationRunOut)
def allocate(project_id: int, db: Session = Depends(get_db)):
    """Schedule + auto-allocate. Idempotent: re-running replaces this project's plan."""
    if not db.get(Project, project_id):
        raise HTTPException(404, "Project not found")
    try:
        result = run_allocation(db, project_id)
    except SchedulingError as exc:
        raise HTTPException(422, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return AllocationRunOut(
        summary=result.summary,
        warnings=result.warnings,
        allocations=[AllocationOut.model_validate(a) for a in result.allocated],
        shortages=[ShortageOut.model_validate(s) for s in result.shortages],
    )


@router.get("/projects/{project_id}/allocations", response_model=list[AllocationOut])
def list_allocations(project_id: int, db: Session = Depends(get_db)):
    return db.scalars(
        select(Allocation)
        .join(Task, Allocation.task_id == Task.id)
        .join(ProjectStage, Task.project_stage_id == ProjectStage.id)
        .where(ProjectStage.project_id == project_id)
    ).all()


@router.get("/projects/{project_id}/shortages", response_model=list[ShortageOut])
def list_shortages(project_id: int, db: Session = Depends(get_db)):
    return db.scalars(select(Shortage).where(Shortage.project_id == project_id)).all()


@router.get("/shortages", response_model=list[ShortageOut])
def list_all_shortages(db: Session = Depends(get_db)):
    return db.scalars(select(Shortage).order_by(Shortage.required_from)).all()


@router.get("/conflicts", response_model=list[ConflictOut])
def list_conflicts(project_id: int | None = None, db: Session = Depends(get_db)):
    """Double-booking check. Should be empty for anything this system allocated."""
    return [
        ConflictOut(
            employee_id=c.employee_id,
            employee_code=c.employee_code,
            employee_name=c.employee_name,
            left=c.left,
            right=c.right,
            overlap_from=c.overlap_from,
            overlap_to=c.overlap_to,
            reason=c.reason(),
        )
        for c in find_conflicts(db, project_id)
    ]
