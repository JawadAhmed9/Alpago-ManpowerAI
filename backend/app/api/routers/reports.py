from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Allocation, Employee, EmployeeStatus, Project, Shortage
from app.services.report_service import build_gantt
from app.services.scheduling_service import SchedulingError

router = APIRouter(tags=["reports"])


@router.get("/projects/{project_id}/gantt")
def project_gantt(project_id: int, db: Session = Depends(get_db)):
    """The Expected Output view, generated dynamically for any project."""
    if not db.get(Project, project_id):
        raise HTTPException(404, "Project not found")
    try:
        return build_gantt(db, project_id)
    except SchedulingError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    return {
        "projects": db.scalar(select(func.count()).select_from(Project)),
        "employees_active": db.scalar(
            select(func.count()).select_from(Employee).where(Employee.status == EmployeeStatus.ACTIVE)
        ),
        "allocations": db.scalar(select(func.count()).select_from(Allocation)),
        "shortages": db.scalar(select(func.count()).select_from(Shortage)),
    }
