"""Shared DB -> engine adapters."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.engine.allocator import Booking, Candidate
from app.engine.workcalendar import WorkCalendar, calendar_for
from app.models import (
    Allocation,
    CalendarRule,
    Category,
    Designation,
    Employee,
    EmployeeStatus,
    Project,
    ProjectStage,
    Task,
)


def load_holidays(db: Session) -> frozenset[date]:
    from app.models import PublicHoliday

    return frozenset(db.scalars(select(PublicHoliday.holiday_date)).all())


def load_calendars(db: Session, holidays: frozenset[date] | None = None) -> dict[Category, WorkCalendar]:
    """One WorkCalendar per employee category, holidays folded in."""
    holidays = load_holidays(db) if holidays is None else holidays
    calendars: dict[Category, WorkCalendar] = {}
    for rule in db.scalars(select(CalendarRule)).all():
        calendars[rule.category] = calendar_for(rule.workdays, holidays, rule.category.value)
    return calendars


def load_candidates(db: Session) -> dict[int, list[Candidate]]:
    """Active, allocatable employees grouped by designation id."""
    rows = db.scalars(
        select(Employee).options(selectinload(Employee.designation)).where(
            Employee.status == EmployeeStatus.ACTIVE
        )
    ).all()
    out: dict[int, list[Candidate]] = {}
    for emp in rows:
        if not emp.designation.allocatable:
            continue
        out.setdefault(emp.designation_id, []).append(
            Candidate(
                employee_id=emp.id,
                employee_code=emp.employee_code,
                name=emp.name,
                designation_id=emp.designation_id,
                designation=emp.designation.name,
                skill_level=emp.skill_level.value,
                date_of_joining=emp.date_of_joining,
                is_active=True,
            )
        )
    return out


def load_all_employees(db: Session) -> dict[int, Candidate]:
    rows = db.scalars(select(Employee).options(selectinload(Employee.designation))).all()
    return {
        e.id: Candidate(
            employee_id=e.id,
            employee_code=e.employee_code,
            name=e.name,
            designation_id=e.designation_id,
            designation=e.designation.name,
            skill_level=e.skill_level.value,
            date_of_joining=e.date_of_joining,
            is_active=e.status == EmployeeStatus.ACTIVE,
        )
        for e in rows
    }


def load_bookings(db: Session, exclude_project_id: int | None = None) -> list[Booking]:
    """Every existing allocation as a booking, optionally minus one project's own.

    Excluding the project being re-planned makes re-running allocation idempotent
    instead of making the project collide with its own previous run.
    """
    stmt = (
        select(Allocation, Project.project_code, Task.name)
        .join(Task, Allocation.task_id == Task.id)
        .join(ProjectStage, Task.project_stage_id == ProjectStage.id)
        .join(Project, ProjectStage.project_id == Project.id)
    )
    if exclude_project_id is not None:
        stmt = stmt.where(ProjectStage.project_id != exclude_project_id)

    return [
        Booking(
            employee_id=alloc.employee_id,
            start=alloc.actual_start_date,
            end=alloc.actual_end_date,
            label=f"{code} / {task_name}",
        )
        for alloc, code, task_name in db.execute(stmt).all()
    ]


def load_project(db: Session, project_id: int) -> Project | None:
    return db.scalars(
        select(Project)
        .options(
            selectinload(Project.stages)
            .selectinload(ProjectStage.tasks)
            .selectinload(Task.designation),
            selectinload(Project.stages).selectinload(ProjectStage.stage),
            selectinload(Project.project_manager),
        )
        .where(Project.id == project_id)
    ).first()


def designation_category(designation: Designation) -> Category:
    return designation.category
