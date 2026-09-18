"""Seed the database straight from TechnicalTest_2.xlsx.

Idempotent: safe to re-run. Sample data only -- every table accepts unlimited
additional rows afterwards.
"""

from __future__ import annotations

import argparse
import re
from datetime import date, datetime
from pathlib import Path

import openpyxl
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import Base, SessionLocal, engine
from app.models import (
    CalendarRule,
    Category,
    Designation,
    Employee,
    EmployeeStatus,
    Priority,
    Project,
    ProjectStage,
    ProjectStatus,
    SkillLevel,
    Stage,
    StageDesignation,
    Task,
    TaskDependency,
)
from app.seed.templates import DEFAULT_STAGE_TEMPLATES, split_budget

WORKBOOK = Path(__file__).with_name("TechnicalTest_2.xlsx")

WHITE = "1,2,3,4,5"
BLUE = "1,2,3,4,5,6"

# Designations that exist as people but are not allocatable production resources.
NON_ALLOCATABLE = {"Project Manager"}


# ---------------------------------------------------------------------------
# parsing helpers -- the workbook mixes real datetimes with strings like
# "01-Sep-2026", and PRJ007's target end date cell is junk. Be forgiving.
# ---------------------------------------------------------------------------
def parse_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text or text in {"0", "00:00:00"}:
        return None
    for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def norm(value) -> str:
    """Normalise dashes/spacing so 'Mon–Fri' and 'Mon-Fri' compare equal."""
    return re.sub(r"\s+", " ", str(value or "").replace("–", "-").replace("—", "-")).strip()


def parse_category(value) -> Category:
    return Category.BLUE_COLLAR if "blue" in norm(value).lower() else Category.WHITE_COLLAR


def parse_skill(value) -> SkillLevel:
    text = norm(value).title()
    return {"Junior": SkillLevel.JUNIOR, "Mid": SkillLevel.MID, "Senior": SkillLevel.SENIOR}.get(
        text, SkillLevel.MID
    )


def parse_priority(value) -> Priority:
    mapping = {
        "low": Priority.LOW,
        "medium": Priority.MEDIUM,
        "high": Priority.HIGH,
        "urgent": Priority.URGENT,
    }
    return mapping.get(norm(value).lower(), Priority.MEDIUM)


# ---------------------------------------------------------------------------
def seed_calendar_rules(db: Session) -> None:
    wanted = [
        CalendarRule(
            category=Category.WHITE_COLLAR,
            workdays=WHITE,
            weekly_off_days="6,7",
            standard_shift_hrs=8,
            overtime_allowed=False,
            notes="Design, Planning, Procurement, Sourcing, QA Engineer, Logistics Coordinator "
            "and other management/engineering roles.",
        ),
        CalendarRule(
            category=Category.BLUE_COLLAR,
            workdays=BLUE,
            weekly_off_days="7",
            standard_shift_hrs=8,
            overtime_allowed=True,
            notes="Manufacturing, QC Inspector, Packing, Dispatch/Driver and other production roles. "
            "Overtime beyond 8 hrs/day or on approved additional days (incl. Sunday if approved).",
        ),
    ]
    existing = {r.category for r in db.scalars(select(CalendarRule)).all()}
    for rule in wanted:
        if rule.category not in existing:
            db.add(rule)
    db.flush()


def seed_masters(db: Session, wb) -> tuple[dict[str, Stage], dict[str, Designation]]:
    ws = wb["Stage-Designation Master"]
    stages: dict[str, Stage] = {s.name: s for s in db.scalars(select(Stage)).all()}
    designations: dict[str, Designation] = {d.name: d for d in db.scalars(select(Designation)).all()}
    links = {
        (link.stage_id, link.designation_id)
        for link in db.scalars(select(StageDesignation)).all()
    }

    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or row[0] is None:
            continue
        seq, stage_name, designation_name, category = int(row[0]), norm(row[1]), norm(row[2]), row[3]
        shift = float(row[6] or 8)
        ot = norm(row[7]).lower().startswith("y")

        stage = stages.get(stage_name)
        if stage is None:
            stage = Stage(name=stage_name, sequence_order=seq)
            db.add(stage)
            stages[stage_name] = stage

        designation = designations.get(designation_name)
        if designation is None:
            designation = Designation(
                name=designation_name,
                category=parse_category(category),
                standard_shift_hrs=shift,
                overtime_applicable=ot,
                allocatable=designation_name not in NON_ALLOCATABLE,
            )
            db.add(designation)
            designations[designation_name] = designation

        db.flush()
        if (stage.id, designation.id) not in links:
            db.add(StageDesignation(stage_id=stage.id, designation_id=designation.id))
            links.add((stage.id, designation.id))
    db.flush()
    return stages, designations


def seed_employees(db: Session, wb, designations: dict[str, Designation]) -> dict[str, Employee]:
    ws = wb["Employee Master (Sample)"]
    existing = {e.employee_code: e for e in db.scalars(select(Employee)).all()}

    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or not row[0]:
            continue
        code, name, designation_name = norm(row[0]), norm(row[1]), norm(row[2])
        if code in existing:
            continue

        designation = designations.get(designation_name)
        if designation is None:
            # Roles that appear only on the employee sheet (e.g. Project Manager)
            # still get a designation row -- just a non-allocatable one.
            designation = Designation(
                name=designation_name,
                category=parse_category(row[4]),
                standard_shift_hrs=8,
                overtime_applicable=norm(row[7]).lower().startswith("y"),
                allocatable=designation_name not in NON_ALLOCATABLE,
            )
            db.add(designation)
            db.flush()
            designations[designation_name] = designation

        employee = Employee(
            employee_code=code,
            name=name,
            designation_id=designation.id,
            skill_level=parse_skill(row[8]),
            date_of_joining=parse_date(row[9]) or date(2020, 1, 1),
            status=EmployeeStatus.ACTIVE
            if norm(row[10]).lower() != "inactive"
            else EmployeeStatus.INACTIVE,
            ot_eligible=norm(row[7]).lower().startswith("y"),
        )
        db.add(employee)
        existing[code] = employee
    db.flush()
    return existing


def seed_projects(
    db: Session,
    wb,
    stages: dict[str, Stage],
    designations: dict[str, Designation],
    employees: dict[str, Employee],
) -> list[Project]:
    ws = wb["Project Master (Sample)"]
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    header = [norm(c) for c in rows[0]]

    # Map "Design (Calendar Days)" -> stage name, positionally, so extra columns
    # or renamed stages do not break the loader.
    stage_columns: list[tuple[int, str]] = []
    for idx, cell in enumerate(header):
        match = re.match(r"^(.*?)\s*\(.*days.*\)$", cell, flags=re.IGNORECASE)
        if match and match.group(1) in stages:
            stage_columns.append((idx, match.group(1)))

    by_name = {e.name: e for e in employees.values()}
    existing = {p.project_code for p in db.scalars(select(Project)).all()}
    created: list[Project] = []

    for row in rows[1:]:
        if not row or not row[0]:
            continue
        code = norm(row[0])
        if code in existing:
            continue
        start = parse_date(row[6])
        if start is None:
            continue

        manager = by_name.get(norm(row[3]))
        project = Project(
            project_code=code,
            name=norm(row[1]),
            client=norm(row[2]) or None,
            project_manager_id=manager.id if manager else None,
            location=norm(row[4]) or None,
            priority=parse_priority(row[5]),
            start_date=start,
            target_end_date=parse_date(row[7]),
            status=ProjectStatus.PLANNED,
        )
        db.add(project)
        db.flush()

        for idx, stage_name in stage_columns:
            budget = row[idx]
            if budget in (None, "", 0):
                continue
            stage = stages[stage_name]
            db.add(
                ProjectStage(
                    project_id=project.id,
                    stage_id=stage.id,
                    sequence_order=stage.sequence_order,
                    man_days_budgeted=int(budget),
                )
            )
        db.flush()
        generate_tasks_from_templates(db, project, designations)
        created.append(project)

    db.flush()
    return created


def generate_tasks_from_templates(
    db: Session, project: Project, designations: dict[str, Designation]
) -> None:
    """Materialise default sub-tasks + dependency edges for every stage.

    A project manager can edit, add or delete these afterwards -- they are plain
    rows, not a hardcoded breakdown.
    """
    project_stages = sorted(
        db.scalars(select(ProjectStage).where(ProjectStage.project_id == project.id)).all(),
        key=lambda ps: ps.sequence_order,
    )
    previous_exits: list[Task] = []

    for ps in project_stages:
        stage_name = db.scalar(select(Stage.name).where(Stage.id == ps.stage_id))
        template = DEFAULT_STAGE_TEMPLATES.get(stage_name)
        if template is None:
            continue

        durations = split_budget(ps.man_days_budgeted, [t.weight for t in template.tasks])
        created: list[Task] = []
        for order, (tpl, duration) in enumerate(zip(template.tasks, durations, strict=True)):
            designation = designations.get(tpl.designation)
            if designation is None:
                raise ValueError(f"Template references unknown designation {tpl.designation!r}")
            task = Task(
                project_stage_id=ps.id,
                name=tpl.name,
                designation_id=designation.id,
                duration_working_days=duration,
                sequence_order=order,
            )
            db.add(task)
            created.append(task)
        db.flush()

        # Intra-stage edges.
        for tpl, task in zip(template.tasks, created, strict=True):
            for pred_index, lag in tpl.predecessors:
                db.add(
                    TaskDependency(
                        predecessor_id=created[pred_index].id, successor_id=task.id, lag_days=lag
                    )
                )

        # Cross-stage edges: tasks with no intra-stage predecessor hang off the
        # previous stage's exit tasks.
        entry_indices = [i for i, tpl in enumerate(template.tasks) if not tpl.predecessors]
        for i in entry_indices:
            for exit_task in previous_exits:
                db.add(
                    TaskDependency(
                        predecessor_id=exit_task.id,
                        successor_id=created[i].id,
                        lag_days=template.entry_lag,
                    )
                )
        db.flush()
        previous_exits = [created[i] for i in template.resolved_exits()]


def run(reset: bool = False) -> None:
    if reset:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    wb = openpyxl.load_workbook(WORKBOOK, data_only=True)
    with SessionLocal() as db:
        seed_calendar_rules(db)
        stages, designations = seed_masters(db, wb)
        employees = seed_employees(db, wb, designations)
        projects = seed_projects(db, wb, stages, designations, employees)
        db.commit()
        print(
            f"Seeded: {len(stages)} stages, {len(designations)} designations, "
            f"{len(employees)} employees, {len(projects)} new projects."
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed the Alpago database from the sample workbook.")
    parser.add_argument("--reset", action="store_true", help="drop and recreate all tables first")
    args = parser.parse_args()
    run(reset=args.reset)
