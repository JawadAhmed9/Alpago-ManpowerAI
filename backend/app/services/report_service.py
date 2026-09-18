"""Gantt matrix report -- a dynamic rebuild of the workbook's Expected Output.

Nothing here is per-project; the same code renders any project of any size.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Allocation, Employee, Shortage
from app.services.context import load_calendars
from app.services.scheduling_service import compute_schedule, validate_stage_budgets

WEEKDAY_LETTERS = {1: "M", 2: "T", 3: "W", 4: "T", 5: "F", 6: "SA", 7: "SU"}


def build_gantt(db: Session, project_id: int) -> dict:
    project, schedule = compute_schedule(db, project_id, persist=False)

    task_ids = [t.id for ps in project.stages for t in ps.tasks]
    allocations = {
        a.task_id: a
        for a in db.scalars(select(Allocation).where(Allocation.task_id.in_(task_ids))).all()
    }
    employees = {
        e.id: e for e in db.scalars(select(Employee).where(Employee.id.in_(
            [a.employee_id for a in allocations.values()] or [0]
        ))).all()
    }
    shortages = {
        s.task_id: s
        for s in db.scalars(select(Shortage).where(Shortage.project_id == project_id)).all()
    }
    stage_names = {str(ps.id): ps.stage.name for ps in project.stages}
    stage_budgets = {str(ps.id): ps.man_days_budgeted for ps in project.stages}
    calendars = load_calendars(db)

    # Column axis: every calendar day in the project span.
    span_start, span_end = schedule.project_start, schedule.project_end
    columns = []
    cursor = span_start
    while cursor <= span_end:
        columns.append(
            {
                "date": cursor.isoformat(),
                "day": cursor.day,
                "month": cursor.strftime("%b %Y"),
                "weekday": WEEKDAY_LETTERS[cursor.isoweekday()],
                "is_weekend_white": cursor.isoweekday() in (6, 7),
                "is_weekend_blue": cursor.isoweekday() == 7,
                "is_holiday": any(cursor in cal.holidays for cal in calendars.values()),
            }
        )
        cursor += timedelta(days=1)

    # Rows: a band per stage, then its tasks.
    rows: list[dict] = []
    ref = 0
    by_stage: dict[str, list] = {}
    for task in schedule.tasks:
        by_stage.setdefault(task.stage_key, []).append(task)

    for stage_key, stage_tasks in sorted(
        by_stage.items(), key=lambda kv: kv[1][0].stage_sequence
    ):
        start = min(t.start for t in stage_tasks)
        end = max(t.end for t in stage_tasks)
        rows.append(
            {
                "kind": "stage",
                "ref": None,
                "label": f"Stage {stage_tasks[0].stage_sequence}: {stage_names[stage_key]}",
                "resource": _stage_resource_label(stage_tasks),
                "days": stage_budgets.get(stage_key),
                "start": start.isoformat(),
                "end": end.isoformat(),
                "cells": {start.isoformat(): stage_names[stage_key]},
                "employee": None,
                "shortage": None,
            }
        )
        for task in stage_tasks:
            ref += 1
            task_id = int(task.key)
            allocation = allocations.get(task_id)
            employee = employees.get(allocation.employee_id) if allocation else None
            shortage = shortages.get(task_id)
            rows.append(
                {
                    "kind": "task",
                    "ref": ref,
                    "task_id": task_id,
                    "label": task.name,
                    "resource": (
                        f"{task.designation} - {employee.name} ({employee.employee_code})"
                        if employee
                        else f"{task.designation} - UNASSIGNED"
                    ),
                    "designation": task.designation,
                    "days": task.duration,
                    "start": task.start.isoformat(),
                    "end": task.end.isoformat(),
                    "cells": {d.isoformat(): n for d, n in zip(task.dates, task.day_numbers, strict=True)},
                    "employee": (
                        {
                            "id": employee.id,
                            "code": employee.employee_code,
                            "name": employee.name,
                            "skill_level": employee.skill_level.value,
                        }
                        if employee
                        else None
                    ),
                    "allocation_id": allocation.id if allocation else None,
                    "shortage": (
                        {"id": shortage.id, "reason": shortage.reason} if shortage else None
                    ),
                }
            )

    return {
        "project": {
            "id": project.id,
            "code": project.project_code,
            "name": project.name,
            "client": project.client,
            "location": project.location,
            "priority": project.priority.value,
            "status": project.status.value,
            "project_manager": project.project_manager.name if project.project_manager else None,
            "start_date": project.start_date.isoformat(),
            "target_end_date": project.target_end_date.isoformat() if project.target_end_date else None,
        },
        "columns": columns,
        "rows": rows,
        "summary": {
            "total_man_days": schedule.total_man_days,
            "actual_working_days": schedule.actual_working_days,
            "calendar_span_days": (span_end - span_start).days + 1,
            "project_start_date": span_start.isoformat(),
            "expected_completion_date": span_end.isoformat(),
            "allocated_tasks": len(allocations),
            "unallocated_tasks": len(schedule.tasks) - len(allocations),
            "shortages": len(shortages),
        },
        "stage_breakdown": [
            {
                "sequence": ps.sequence_order,
                "stage": ps.stage.name,
                "man_days_budgeted": ps.man_days_budgeted,
                "man_days_planned": sum(t.duration_working_days for t in ps.tasks),
                "start": schedule.stage_windows[str(ps.id)][0].isoformat()
                if str(ps.id) in schedule.stage_windows
                else None,
                "end": schedule.stage_windows[str(ps.id)][1].isoformat()
                if str(ps.id) in schedule.stage_windows
                else None,
            }
            for ps in sorted(project.stages, key=lambda s: s.sequence_order)
        ],
        "warnings": validate_stage_budgets(project),
    }


def _stage_resource_label(stage_tasks: list) -> str:
    stage = stage_tasks[0].stage_name
    return {
        "Design": "Design Team (White Collar)",
        "Planning": "Planning Team (White Collar)",
        "Procurement": "Procurement Team (White Collar)",
        "Sourcing": "Sourcing Team (White Collar)",
        "Manufacturing": "Production Floor (Blue Collar)",
        "Quality Control": "QA/QC Team (Mixed)",
        "Packing": "Packing Team (Blue Collar)",
        "Shipping": "Logistics Team (Mixed)",
    }.get(stage, f"{stage} Team")
