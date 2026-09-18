"""Pydantic request/response models."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import (
    AllocationStatus,
    Category,
    EmployeeStatus,
    Priority,
    ProjectStatus,
    SkillLevel,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- masters ---------------------------------------------------------------
class DesignationOut(ORMModel):
    id: int
    name: str
    category: Category
    standard_shift_hrs: float
    overtime_applicable: bool
    allocatable: bool


class DesignationIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    category: Category
    standard_shift_hrs: float = 8.0
    overtime_applicable: bool = False
    allocatable: bool = True


class StageOut(ORMModel):
    id: int
    name: str
    sequence_order: int


class DesignationUpdate(BaseModel):
    name: str | None = None
    category: Category | None = None
    standard_shift_hrs: float | None = None
    overtime_applicable: bool | None = None
    allocatable: bool | None = None


class StageIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    sequence_order: int


class StageUpdate(BaseModel):
    name: str | None = None
    sequence_order: int | None = None


class StageDesignationIn(BaseModel):
    designation_id: int


class CalendarRuleOut(ORMModel):
    id: int
    category: Category
    workdays: str
    weekly_off_days: str
    standard_shift_hrs: float
    overtime_allowed: bool
    notes: str | None = None


class CalendarRuleUpdate(BaseModel):
    workdays: str | None = None
    weekly_off_days: str | None = None
    standard_shift_hrs: float | None = None
    overtime_allowed: bool | None = None
    notes: str | None = None


class HolidayOut(ORMModel):
    id: int
    holiday_date: date
    label: str


class HolidayIn(BaseModel):
    holiday_date: date
    label: str = Field(min_length=1, max_length=160)


# --- employees -------------------------------------------------------------
class EmployeeOut(ORMModel):
    id: int
    employee_code: str
    name: str
    designation_id: int
    skill_level: SkillLevel
    date_of_joining: date
    status: EmployeeStatus
    ot_eligible: bool
    designation: DesignationOut


class EmployeeIn(BaseModel):
    employee_code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=160)
    designation_id: int
    skill_level: SkillLevel = SkillLevel.MID
    date_of_joining: date
    status: EmployeeStatus = EmployeeStatus.ACTIVE
    ot_eligible: bool = False


class EmployeeUpdate(BaseModel):
    name: str | None = None
    designation_id: int | None = None
    skill_level: SkillLevel | None = None
    date_of_joining: date | None = None
    status: EmployeeStatus | None = None
    ot_eligible: bool | None = None


# --- projects --------------------------------------------------------------
class TaskOut(ORMModel):
    id: int
    name: str
    designation_id: int
    duration_working_days: int
    sequence_order: int
    earliest_start_date: date | None = None


class TaskIn(BaseModel):
    name: str = Field(min_length=1, max_length=240)
    designation_id: int
    duration_working_days: int = Field(gt=0)
    sequence_order: int = 0
    earliest_start_date: date | None = None
    predecessor_ids: list[int] = Field(default_factory=list)
    lag_days: int = 0


class TaskUpdate(BaseModel):
    name: str | None = None
    designation_id: int | None = None
    duration_working_days: int | None = Field(default=None, gt=0)
    sequence_order: int | None = None
    earliest_start_date: date | None = None


class ProjectStageOut(ORMModel):
    id: int
    stage_id: int
    sequence_order: int
    man_days_budgeted: int
    stage_start_date: date | None = None
    stage_end_date: date | None = None
    stage: StageOut
    tasks: list[TaskOut] = Field(default_factory=list)


class ProjectStageIn(BaseModel):
    stage_id: int
    man_days_budgeted: int = Field(gt=0)


class ProjectOut(ORMModel):
    id: int
    project_code: str
    name: str
    client: str | None = None
    project_manager_id: int | None = None
    location: str | None = None
    priority: Priority
    start_date: date
    target_end_date: date | None = None
    status: ProjectStatus


class ProjectDetailOut(ProjectOut):
    stages: list[ProjectStageOut] = Field(default_factory=list)


class ProjectIn(BaseModel):
    project_code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=240)
    client: str | None = None
    project_manager_id: int | None = None
    location: str | None = None
    priority: Priority = Priority.MEDIUM
    start_date: date
    target_end_date: date | None = None
    status: ProjectStatus = ProjectStatus.PLANNED
    # Stage budgets, keyed by stage name, e.g. {"Design": 5, "Manufacturing": 48}.
    # Tasks are generated from the default templates when this is supplied.
    stage_budgets: dict[str, int] = Field(default_factory=dict)


class ProjectUpdate(BaseModel):
    name: str | None = None
    client: str | None = None
    project_manager_id: int | None = None
    location: str | None = None
    priority: Priority | None = None
    start_date: date | None = None
    target_end_date: date | None = None
    status: ProjectStatus | None = None


# --- allocation ------------------------------------------------------------
class AllocationOut(ORMModel):
    id: int
    task_id: int
    employee_id: int
    actual_start_date: date
    actual_end_date: date
    working_days: int
    status: AllocationStatus
    score: float | None = None
    score_breakdown: str | None = None


class ShortageOut(ORMModel):
    id: int
    project_id: int
    task_id: int
    designation_id: int
    required_from: date
    required_to: date
    eligible_headcount: int
    available_headcount: int
    earliest_available_date: date | None = None
    reason: str


class ConflictOut(BaseModel):
    employee_id: int
    employee_code: str
    employee_name: str
    left: str
    right: str
    overlap_from: date
    overlap_to: date
    reason: str


class AllocationRunOut(BaseModel):
    summary: dict
    warnings: list[str]
    allocations: list[AllocationOut]
    shortages: list[ShortageOut]


class InsightOut(BaseModel):
    id: int
    related_type: str
    related_id: int
    text: str
    model: str | None = None
    generated_at: datetime | None = None


class InsightRunOut(BaseModel):
    project_id: int
    source: str
    ai_available: bool
    note: str | None = None
    insights: list[InsightOut]
