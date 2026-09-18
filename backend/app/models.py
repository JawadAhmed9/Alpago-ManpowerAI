"""SQLAlchemy data layer.

Design notes
------------
* Nothing is hardcoded to the sample sizes in TechnicalTest_2.xlsx. Stages,
  designations, employees, projects, stage/task definitions and holidays are all
  ordinary rows.
* ``ProjectStage.man_days_budgeted`` deliberately replaces the workbook's
  "(Calendar Days)" wording. See ARCHITECTURE.md -- the sample data proves the
  number is a man-day budget that the stage's tasks partition, not a window
  length.
* The one-employee-one-slot rule is enforced in the service layer AND backed by
  a DB index so a bad import cannot silently create a double booking.
"""

from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Category(str, enum.Enum):
    WHITE_COLLAR = "White Collar"
    BLUE_COLLAR = "Blue Collar"


class SkillLevel(str, enum.Enum):
    JUNIOR = "Junior"
    MID = "Mid"
    SENIOR = "Senior"


class EmployeeStatus(str, enum.Enum):
    ACTIVE = "Active"
    INACTIVE = "Inactive"


class ProjectStatus(str, enum.Enum):
    PLANNED = "Planned"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"
    ON_HOLD = "On Hold"


class Priority(str, enum.Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    URGENT = "Urgent"


class AllocationStatus(str, enum.Enum):
    PLANNED = "Planned"
    IN_PROGRESS = "In Progress"
    DONE = "Done"


class InsightType(str, enum.Enum):
    ALLOCATION = "allocation"
    SHORTAGE = "shortage"
    CONFLICT = "conflict"
    RUN_SUMMARY = "run_summary"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# --------------------------------------------------------------------------
# Master data
# --------------------------------------------------------------------------
class CalendarRule(Base, TimestampMixin):
    """Weekly working pattern per employee category. Admin-editable."""

    __tablename__ = "calendar_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[Category] = mapped_column(Enum(Category), unique=True)
    # ISO weekday numbers that are WORKED: Mon=1 ... Sun=7
    workdays: Mapped[str] = mapped_column(String(32))
    weekly_off_days: Mapped[str] = mapped_column(String(32))
    standard_shift_hrs: Mapped[float] = mapped_column(Float, default=8.0)
    overtime_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    @property
    def workday_set(self) -> set[int]:
        return {int(x) for x in self.workdays.split(",") if x.strip()}


class Designation(Base, TimestampMixin):
    __tablename__ = "designations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    category: Mapped[Category] = mapped_column(Enum(Category))
    standard_shift_hrs: Mapped[float] = mapped_column(Float, default=8.0)
    overtime_applicable: Mapped[bool] = mapped_column(Boolean, default=False)
    # Managers etc. exist as designations but are not allocatable production roles.
    allocatable: Mapped[bool] = mapped_column(Boolean, default=True)

    employees: Mapped[list[Employee]] = relationship(back_populates="designation")
    stage_links: Mapped[list[StageDesignation]] = relationship(
        back_populates="designation", cascade="all, delete-orphan"
    )


class Stage(Base, TimestampMixin):
    __tablename__ = "stages"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    sequence_order: Mapped[int] = mapped_column(Integer, unique=True)

    designation_links: Mapped[list[StageDesignation]] = relationship(
        back_populates="stage", cascade="all, delete-orphan"
    )


class StageDesignation(Base):
    """Which designations are valid inside which stage."""

    __tablename__ = "stage_designations"
    __table_args__ = (UniqueConstraint("stage_id", "designation_id", name="uq_stage_designation"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    stage_id: Mapped[int] = mapped_column(ForeignKey("stages.id", ondelete="CASCADE"))
    designation_id: Mapped[int] = mapped_column(ForeignKey("designations.id", ondelete="CASCADE"))

    stage: Mapped[Stage] = relationship(back_populates="designation_links")
    designation: Mapped[Designation] = relationship(back_populates="stage_links")


class PublicHoliday(Base, TimestampMixin):
    """Admin-configurable. Applies to every category, on top of weekly offs."""

    __tablename__ = "public_holidays"

    id: Mapped[int] = mapped_column(primary_key=True)
    holiday_date: Mapped[date] = mapped_column(Date, unique=True)
    label: Mapped[str] = mapped_column(String(160))


class Employee(Base, TimestampMixin):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    designation_id: Mapped[int] = mapped_column(ForeignKey("designations.id"), index=True)
    skill_level: Mapped[SkillLevel] = mapped_column(Enum(SkillLevel), default=SkillLevel.MID)
    date_of_joining: Mapped[date] = mapped_column(Date)
    status: Mapped[EmployeeStatus] = mapped_column(
        Enum(EmployeeStatus), default=EmployeeStatus.ACTIVE, index=True
    )
    ot_eligible: Mapped[bool] = mapped_column(Boolean, default=False)

    designation: Mapped[Designation] = relationship(back_populates="employees")
    allocations: Mapped[list[Allocation]] = relationship(back_populates="employee")

    @property
    def category(self) -> Category:
        return self.designation.category


# --------------------------------------------------------------------------
# Project structure
# --------------------------------------------------------------------------
class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(240))
    client: Mapped[str | None] = mapped_column(String(240), nullable=True)
    project_manager_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    location: Mapped[str | None] = mapped_column(String(240), nullable=True)
    priority: Mapped[Priority] = mapped_column(Enum(Priority), default=Priority.MEDIUM)
    start_date: Mapped[date] = mapped_column(Date)
    target_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[ProjectStatus] = mapped_column(Enum(ProjectStatus), default=ProjectStatus.PLANNED)

    project_manager: Mapped[Employee | None] = relationship(foreign_keys=[project_manager_id])
    stages: Mapped[list[ProjectStage]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="ProjectStage.sequence_order"
    )


class ProjectStage(Base, TimestampMixin):
    """One stage instance inside one project.

    ``man_days_budgeted`` is the workbook's per-stage number. The stage's tasks
    must partition it (sum of task durations == budget) -- validated, not assumed.
    """

    __tablename__ = "project_stages"
    __table_args__ = (UniqueConstraint("project_id", "stage_id", name="uq_project_stage"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    stage_id: Mapped[int] = mapped_column(ForeignKey("stages.id"))
    sequence_order: Mapped[int] = mapped_column(Integer)
    man_days_budgeted: Mapped[int] = mapped_column(Integer)
    # Derived by the scheduler; persisted so reports do not have to recompute.
    stage_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    stage_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    project: Mapped[Project] = relationship(back_populates="stages")
    stage: Mapped[Stage] = relationship()
    tasks: Mapped[list[Task]] = relationship(
        back_populates="project_stage", cascade="all, delete-orphan", order_by="Task.sequence_order"
    )


class Task(Base, TimestampMixin):
    """A named sub-task a project manager defines inside a stage instance.

    ``duration_working_days`` is man-days for ONE person (the workbook's "Days"
    column on the Expected Output sheet).
    """

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_stage_id: Mapped[int] = mapped_column(
        ForeignKey("project_stages.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(240))
    designation_id: Mapped[int] = mapped_column(ForeignKey("designations.id"))
    duration_working_days: Mapped[int] = mapped_column(Integer)
    sequence_order: Mapped[int] = mapped_column(Integer)
    # Optional manual pin; when set the scheduler will not move the task earlier.
    earliest_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    project_stage: Mapped[ProjectStage] = relationship(back_populates="tasks")
    designation: Mapped[Designation] = relationship()
    allocation: Mapped[Allocation | None] = relationship(
        back_populates="task", cascade="all, delete-orphan", uselist=False
    )
    predecessor_links: Mapped[list[TaskDependency]] = relationship(
        back_populates="successor",
        foreign_keys="TaskDependency.successor_id",
        cascade="all, delete-orphan",
    )

    __table_args__ = (CheckConstraint("duration_working_days > 0", name="ck_task_duration_positive"),)


class TaskDependency(Base):
    """Finish-to-start edge with optional lag.

    ``lag_days`` is in working days. Negative lag == overlap, which is exactly how
    the sample's Design stage behaves (CAD detailing starts on the last day of
    concept design).
    """

    __tablename__ = "task_dependencies"
    __table_args__ = (
        UniqueConstraint("predecessor_id", "successor_id", name="uq_task_edge"),
        CheckConstraint("predecessor_id != successor_id", name="ck_no_self_dependency"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    predecessor_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    successor_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    lag_days: Mapped[int] = mapped_column(Integer, default=0)

    predecessor: Mapped[Task] = relationship(foreign_keys=[predecessor_id])
    successor: Mapped[Task] = relationship(foreign_keys=[successor_id], back_populates="predecessor_links")


# --------------------------------------------------------------------------
# Allocation + AI output
# --------------------------------------------------------------------------
class Allocation(Base, TimestampMixin):
    __tablename__ = "allocations"
    __table_args__ = (
        UniqueConstraint("task_id", name="uq_allocation_task"),
        Index("ix_allocation_employee_window", "employee_id", "actual_start_date", "actual_end_date"),
        CheckConstraint("actual_end_date >= actual_start_date", name="ck_allocation_window"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    actual_start_date: Mapped[date] = mapped_column(Date)
    actual_end_date: Mapped[date] = mapped_column(Date)
    working_days: Mapped[int] = mapped_column(Integer)
    status: Mapped[AllocationStatus] = mapped_column(
        Enum(AllocationStatus), default=AllocationStatus.PLANNED
    )
    # Audit trail for the deterministic pick -- no LLM involved.
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_breakdown: Mapped[str | None] = mapped_column(Text, nullable=True)

    task: Mapped[Task] = relationship(back_populates="allocation")
    employee: Mapped[Employee] = relationship(back_populates="allocations")


class Shortage(Base, TimestampMixin):
    """Raised when zero eligible+available employees exist for a task window."""

    __tablename__ = "shortages"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))
    designation_id: Mapped[int] = mapped_column(ForeignKey("designations.id"))
    required_from: Mapped[date] = mapped_column(Date)
    required_to: Mapped[date] = mapped_column(Date)
    eligible_headcount: Mapped[int] = mapped_column(Integer, default=0)
    available_headcount: Mapped[int] = mapped_column(Integer, default=0)
    earliest_available_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    reason: Mapped[str] = mapped_column(Text)

    task: Mapped[Task] = relationship()
    designation: Mapped[Designation] = relationship()


class AIInsight(Base):
    """Cached LLM output. Generated on demand, never on page load."""

    __tablename__ = "ai_insights"
    __table_args__ = (Index("ix_insight_lookup", "related_type", "related_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    related_type: Mapped[InsightType] = mapped_column(Enum(InsightType))
    related_id: Mapped[int] = mapped_column(Integer)
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=True
    )
    text: Mapped[str] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
