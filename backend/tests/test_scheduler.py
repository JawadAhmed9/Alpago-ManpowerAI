from datetime import date

import pytest

from app.engine.scheduler import (
    CyclicDependencyError,
    TaskSpec,
    schedule_project,
)
from app.engine.workcalendar import BLUE_COLLAR_WORKDAYS, WHITE_COLLAR_WORKDAYS, WorkCalendar

WC = WorkCalendar(WHITE_COLLAR_WORKDAYS, frozenset(), "WC")
BC = WorkCalendar(BLUE_COLLAR_WORKDAYS, frozenset(), "BC")


def spec(key, duration, cal=WC, preds=(), order=0, stage=1):
    return TaskSpec(
        key=key,
        name=key,
        duration=duration,
        calendar=cal,
        stage_key=f"s{stage}",
        stage_name=f"Stage {stage}",
        stage_sequence=stage,
        sequence_order=order,
        designation="Role",
        predecessors=list(preds),
    )


def test_negative_lag_creates_a_one_day_overlap():
    schedule = schedule_project(
        date(2026, 9, 1), [spec("a", 3), spec("b", 2, preds=[("a", -1)], order=1)]
    )
    tasks = schedule.by_key()
    assert tasks["a"].end == date(2026, 9, 3)
    assert tasks["b"].start == date(2026, 9, 3)


def test_zero_lag_starts_the_next_working_day():
    schedule = schedule_project(
        date(2026, 9, 1), [spec("a", 4), spec("b", 1, preds=[("a", 0)], order=1)]
    )
    assert schedule.by_key()["b"].start == date(2026, 9, 7)  # Mon after Fri 4-Sep


def test_parallel_tasks_share_the_same_day_numbers():
    schedule = schedule_project(
        date(2026, 9, 1), [spec("a", 3, BC), spec("b", 3, BC, order=1)]
    )
    tasks = schedule.by_key()
    assert tasks["a"].day_numbers == tasks["b"].day_numbers == [1, 2, 3]
    assert schedule.total_man_days == 6
    assert schedule.actual_working_days == 3


def test_a_task_waits_for_its_latest_predecessor():
    schedule = schedule_project(
        date(2026, 9, 1),
        [
            spec("a", 3, BC),
            spec("b", 10, BC, order=1),
            spec("c", 1, BC, preds=[("a", 0), ("b", 0)], order=2),
        ],
    )
    tasks = schedule.by_key()
    assert tasks["c"].start > tasks["b"].end
    assert tasks["c"].day_numbers == [11]


def test_cycles_are_rejected():
    with pytest.raises(CyclicDependencyError):
        schedule_project(
            date(2026, 9, 1),
            [spec("a", 1, preds=[("b", 0)]), spec("b", 1, preds=[("a", 0)], order=1)],
        )


def test_unknown_predecessor_is_rejected():
    with pytest.raises(ValueError, match="unknown task"):
        schedule_project(date(2026, 9, 1), [spec("a", 1, preds=[("ghost", 0)])])


def test_holiday_shifts_downstream_tasks():
    holiday_cal = WorkCalendar(WHITE_COLLAR_WORKDAYS, frozenset({date(2026, 9, 2)}), "WC")
    schedule = schedule_project(
        date(2026, 9, 1),
        [
            TaskSpec("a", "a", 3, holiday_cal, "s1", "S1", 1, 0, "R"),
            TaskSpec("b", "b", 1, holiday_cal, "s1", "S1", 1, 1, "R", [("a", 0)]),
        ],
    )
    tasks = schedule.by_key()
    assert tasks["a"].end == date(2026, 9, 4)
    assert tasks["b"].start == date(2026, 9, 7)
