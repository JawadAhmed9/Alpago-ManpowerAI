"""Run allocation for a project and persist the results."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import settings
from app.engine.allocator import (
    Allocator,
    Booking,
    BookingIndex,
    ConflictFinding,
    ShortageFinding,
    detect_conflicts,
)
from app.engine.scheduler import ProjectSchedule
from app.models import Allocation, AllocationStatus, Project, ProjectStage, Shortage, Task
from app.services.context import (
    load_all_employees,
    load_bookings,
    load_candidates,
)
from app.services.scheduling_service import compute_schedule, validate_stage_budgets


@dataclass
class AllocationRunResult:
    project: Project
    schedule: ProjectSchedule
    allocated: list[Allocation] = field(default_factory=list)
    shortages: list[Shortage] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def summary(self) -> dict:
        return {
            "project_code": self.project.project_code,
            "tasks": len(self.schedule.tasks),
            "allocated": len(self.allocated),
            "shortages": len(self.shortages),
            "total_man_days": self.schedule.total_man_days,
            "actual_working_days": self.schedule.actual_working_days,
            "project_start": self.schedule.project_start.isoformat(),
            "project_end": self.schedule.project_end.isoformat(),
        }


def run_allocation(db: Session, project_id: int) -> AllocationRunResult:
    """Schedule the project, then assign the best free employee to every task.

    Re-runnable: the project's own previous allocations are cleared first, so a
    second run never collides with itself.
    """
    project, schedule = compute_schedule(db, project_id, persist=True)
    warnings = validate_stage_budgets(project)

    task_ids = [t.id for ps in project.stages for t in ps.tasks]
    db.execute(delete(Allocation).where(Allocation.task_id.in_(task_ids)))
    db.execute(delete(Shortage).where(Shortage.project_id == project_id))
    db.flush()

    tasks_by_id = {str(t.id): t for ps in project.stages for t in ps.tasks}
    allocator = Allocator(
        candidates_by_designation=load_candidates(db),
        booking_index=BookingIndex(load_bookings(db, exclude_project_id=project_id)),
        skill_weights={
            "Senior": settings.skill_weight_senior,
            "Mid": settings.skill_weight_mid,
            "Junior": settings.skill_weight_junior,
        },
        workload_penalty_per_day=settings.workload_penalty_per_day,
    )

    allocated: list[Allocation] = []
    shortages: list[Shortage] = []

    for scheduled in schedule.tasks:
        task = tasks_by_id[scheduled.key]
        outcome = allocator.allocate(
            task_key=scheduled.key,
            designation_id=task.designation_id,
            designation_name=task.designation.name,
            start=scheduled.start,
            end=scheduled.end,
        )
        if isinstance(outcome, ShortageFinding):
            row = Shortage(
                project_id=project_id,
                task_id=task.id,
                designation_id=task.designation_id,
                required_from=outcome.required_from,
                required_to=outcome.required_to,
                eligible_headcount=outcome.eligible_headcount,
                available_headcount=0,
                earliest_available_date=outcome.earliest_available_date,
                reason=outcome.reason(),
            )
            db.add(row)
            shortages.append(row)
            continue

        row = Allocation(
            task_id=task.id,
            employee_id=outcome.employee.employee_id,
            actual_start_date=outcome.start,
            actual_end_date=outcome.end,
            working_days=scheduled.duration,
            status=AllocationStatus.PLANNED,
            score=outcome.score,
            score_breakdown=json.dumps(
                {
                    **outcome.breakdown.as_dict(),
                    "reason": outcome.reason(),
                    "runners_up": outcome.runners_up,
                }
            ),
        )
        db.add(row)
        allocated.append(row)

    db.flush()
    return AllocationRunResult(
        project=project, schedule=schedule, allocated=allocated, shortages=shortages, warnings=warnings
    )


def find_conflicts(db: Session, project_id: int | None = None) -> list[ConflictFinding]:
    """Query for double-bookings across the whole system (or one project's people)."""
    stmt = (
        select(
            Allocation.employee_id,
            Allocation.actual_start_date,
            Allocation.actual_end_date,
            Project.project_code,
            Task.name,
        )
        .join(Task, Allocation.task_id == Task.id)
        .join(ProjectStage, Task.project_stage_id == ProjectStage.id)
        .join(Project, ProjectStage.project_id == Project.id)
    )
    rows = db.execute(stmt).all()

    if project_id is not None:
        involved = {
            r.employee_id for r in rows if r.project_code == _code_for(db, project_id)
        }
        rows = [r for r in rows if r.employee_id in involved]

    bookings = [
        Booking(r.employee_id, r.actual_start_date, r.actual_end_date, f"{r.project_code} / {r.name}")
        for r in rows
    ]
    return detect_conflicts(bookings, load_all_employees(db))


def _code_for(db: Session, project_id: int) -> str | None:
    return db.scalar(select(Project.project_code).where(Project.id == project_id))


def employee_workload(db: Session, employee_id: int) -> list[dict]:
    stmt = (
        select(Allocation, Project.project_code, Project.name, Task.name)
        .join(Task, Allocation.task_id == Task.id)
        .join(ProjectStage, Task.project_stage_id == ProjectStage.id)
        .join(Project, ProjectStage.project_id == Project.id)
        .where(Allocation.employee_id == employee_id)
        .order_by(Allocation.actual_start_date)
    )
    return [
        {
            "allocation_id": a.id,
            "project_code": code,
            "project_name": pname,
            "task": tname,
            "start": a.actual_start_date,
            "end": a.actual_end_date,
            "working_days": a.working_days,
            "status": a.status.value,
        }
        for a, code, pname, tname in db.execute(stmt).all()
    ]
