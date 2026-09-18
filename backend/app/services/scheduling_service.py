"""Build scheduler input from the DB and persist derived stage windows."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.engine.scheduler import ProjectSchedule, TaskSpec, schedule_project
from app.models import Project, TaskDependency
from app.services.context import load_calendars, load_project


class SchedulingError(ValueError):
    pass


def build_task_specs(db: Session, project: Project) -> list[TaskSpec]:
    calendars = load_calendars(db)
    task_ids = [t.id for ps in project.stages for t in ps.tasks]
    if not task_ids:
        raise SchedulingError(f"Project {project.project_code} has no tasks defined")

    edges = db.scalars(
        select(TaskDependency).where(TaskDependency.successor_id.in_(task_ids))
    ).all()
    preds: dict[int, list[tuple[str, int]]] = {}
    for edge in edges:
        preds.setdefault(edge.successor_id, []).append((str(edge.predecessor_id), edge.lag_days))

    specs: list[TaskSpec] = []
    for ps in sorted(project.stages, key=lambda s: s.sequence_order):
        for task in sorted(ps.tasks, key=lambda t: t.sequence_order):
            category = task.designation.category
            calendar = calendars.get(category)
            if calendar is None:
                raise SchedulingError(f"No calendar rule configured for category {category.value}")
            specs.append(
                TaskSpec(
                    key=str(task.id),
                    name=task.name,
                    duration=task.duration_working_days,
                    calendar=calendar,
                    stage_key=str(ps.id),
                    stage_name=ps.stage.name,
                    stage_sequence=ps.sequence_order,
                    sequence_order=task.sequence_order,
                    designation=task.designation.name,
                    predecessors=preds.get(task.id, []),
                    earliest_start=task.earliest_start_date,
                )
            )
    return specs


def compute_schedule(db: Session, project_id: int, persist: bool = True) -> tuple[Project, ProjectSchedule]:
    project = load_project(db, project_id)
    if project is None:
        raise SchedulingError(f"Project {project_id} not found")

    schedule = schedule_project(project.start_date, build_task_specs(db, project))

    if persist:
        for ps in project.stages:
            window = schedule.stage_windows.get(str(ps.id))
            if window:
                ps.stage_start_date, ps.stage_end_date = window
        db.flush()
    return project, schedule


def validate_stage_budgets(project: Project) -> list[str]:
    """Tasks must partition the stage's man-day budget. Reported, never silently fixed."""
    problems: list[str] = []
    for ps in project.stages:
        total = sum(t.duration_working_days for t in ps.tasks)
        if not ps.tasks:
            problems.append(f"{ps.stage.name}: no tasks defined (budget {ps.man_days_budgeted} man-days)")
        elif total != ps.man_days_budgeted:
            problems.append(
                f"{ps.stage.name}: task durations sum to {total} man-days but the stage budget "
                f"is {ps.man_days_budgeted}"
            )
    return problems
