"""Golden regression against the workbook's 'Expected Output' sheet.

Every date below was read straight off the sample grid for PRJ007. Two documented
divergences from the sheet's own summary block are asserted deliberately -- see
ARCHITECTURE.md, "Known errors in the sample".
"""

from datetime import date

import pytest

from app.services.allocation_service import find_conflicts, run_allocation
from app.services.report_service import build_gantt

# (task name, duration, start, end) -- from the Expected Output grid cells.
EXPECTED = [
    ("Concept design & drawings", 3, date(2026, 9, 1), date(2026, 9, 3)),
    ("CAD detailing & shop drawings", 2, date(2026, 9, 3), date(2026, 9, 4)),
    ("Production planning & scheduling", 5, date(2026, 9, 7), date(2026, 9, 11)),
    ("Material & BOQ procurement", 5, date(2026, 9, 14), date(2026, 9, 18)),
    ("Vendor & supplier sourcing", 3, date(2026, 9, 21), date(2026, 9, 23)),
    ("Carpentry & assembly", 15, date(2026, 9, 24), date(2026, 10, 10)),
    ("CNC cutting & edge banding", 10, date(2026, 9, 24), date(2026, 10, 5)),
    ("Welding & metal fabrication", 11, date(2026, 10, 6), date(2026, 10, 17)),
    ("Finishing & polishing", 12, date(2026, 10, 12), date(2026, 10, 24)),
    ("In-line quality inspection", 1, date(2026, 10, 24), date(2026, 10, 24)),
    ("Final QA sign-off", 1, date(2026, 10, 26), date(2026, 10, 26)),
    ("Packing & crating", 3, date(2026, 10, 26), date(2026, 10, 28)),
    ("Dispatch coordination", 1, date(2026, 10, 29), date(2026, 10, 29)),
    ("Loading & transport", 2, date(2026, 10, 30), date(2026, 10, 31)),
]


@pytest.fixture(scope="module")
def run(seeded_db, prj007):
    result = run_allocation(seeded_db, prj007)
    seeded_db.commit()
    return result


def test_task_count(run):
    assert len(run.schedule.tasks) == len(EXPECTED)


@pytest.mark.parametrize(("name", "duration", "start", "end"), EXPECTED)
def test_every_task_window_matches_the_sheet(run, name, duration, start, end):
    task = next(t for t in run.schedule.tasks if t.name == name)
    assert (task.duration, task.start, task.end) == (duration, start, end)


def test_total_man_days_matches_the_sheet(run):
    # Sheet: "Total Man Power Days = 74". Sum of every employee's own day count.
    assert run.schedule.total_man_days == 74


def test_project_span_matches_the_sheet(run):
    assert run.schedule.project_start == date(2026, 9, 1)
    assert run.schedule.project_end == date(2026, 10, 31)


def test_actual_working_days_is_52_not_the_sheets_51(run):
    """The sheet says 51. It is wrong by one.

    Its cumulative counter is consistent up to 'Finishing & polishing', which ends
    at 45 on 24-Oct. 'In-line quality inspection' then restarts at 45 instead of
    46 and the slip propagates to the end. 52 is the arithmetically correct value.
    """
    assert run.schedule.actual_working_days == 52


def test_stage_budgets_are_fully_partitioned(run):
    assert run.warnings == []


def test_every_task_is_allocated(run):
    assert len(run.allocated) == 14
    assert run.shortages == []


def test_assigned_designations_are_valid_for_their_stage(run, seeded_db):
    from sqlalchemy import select

    from app.models import Employee, StageDesignation

    valid = {
        (link.stage_id, link.designation_id)
        for link in seeded_db.scalars(select(StageDesignation)).all()
    }
    for allocation in run.allocated:
        employee = seeded_db.get(Employee, allocation.employee_id)
        stage_id = allocation.task.project_stage.stage_id
        assert (stage_id, employee.designation_id) in valid
        assert employee.designation_id == allocation.task.designation_id


def test_no_employee_is_double_booked(seeded_db, run):
    assert find_conflicts(seeded_db) == []


def test_gantt_axis_matches_the_sheets_61_columns(seeded_db, prj007, run):
    gantt = build_gantt(seeded_db, prj007)
    assert len(gantt["columns"]) == 61
    assert gantt["columns"][0]["date"] == "2026-09-01"
    assert gantt["columns"][-1]["date"] == "2026-10-31"
    # 8 stage bands + 14 task rows
    assert len(gantt["rows"]) == 22
    assert gantt["summary"]["total_man_days"] == 74


def test_gantt_weekday_letters_match_the_sheet(seeded_db, prj007):
    gantt = build_gantt(seeded_db, prj007)
    letters = [c["weekday"] for c in gantt["columns"][:7]]
    assert letters == ["T", "W", "T", "F", "SA", "SU", "M"]
