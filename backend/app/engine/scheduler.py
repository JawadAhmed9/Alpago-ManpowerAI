"""Deterministic scheduling engine.

Turns a project's stage/task definitions into concrete calendar windows by
walking the task DAG in topological order and applying each task's category
calendar. 100%% rule-based -- no LLM anywhere near the date math.

Dependency semantics
--------------------
Every edge is finish-to-start with a lag expressed in *working days*:

    successor.start = successor_calendar.advance(predecessor.end, 1 + lag)

so ``lag == 0`` starts the successor on the next working day, and ``lag == -1``
starts it on the predecessor's final day (a one-day overlap). That single knob
reproduces the workbook's Design stage ("CAD detailing" starts on the last day
of "Concept design") and its in-line QC inspection.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import date

from app.engine.workcalendar import WorkCalendar


class CyclicDependencyError(ValueError):
    """Raised when the task graph is not a DAG."""


@dataclass
class TaskSpec:
    """Scheduler input. Deliberately decoupled from the ORM."""

    key: str
    name: str
    duration: int
    calendar: WorkCalendar
    stage_key: str
    stage_name: str
    stage_sequence: int
    sequence_order: int
    designation: str
    predecessors: list[tuple[str, int]] = field(default_factory=list)  # (predecessor_key, lag_days)
    earliest_start: date | None = None


@dataclass
class ScheduledTask:
    key: str
    name: str
    stage_key: str
    stage_name: str
    stage_sequence: int
    sequence_order: int
    designation: str
    duration: int
    start: date
    end: date
    dates: list[date]
    # Cumulative working-day index of the project timeline (the workbook's cell
    # numbers). day_index[i] corresponds to dates[i].
    day_numbers: list[int] = field(default_factory=list)

    @property
    def first_day_number(self) -> int:
        return self.day_numbers[0] if self.day_numbers else 0

    @property
    def last_day_number(self) -> int:
        return self.day_numbers[-1] if self.day_numbers else 0


@dataclass
class ProjectSchedule:
    tasks: list[ScheduledTask]
    stage_windows: dict[str, tuple[date, date]]
    project_start: date
    project_end: date
    total_man_days: int
    actual_working_days: int

    def by_key(self) -> dict[str, ScheduledTask]:
        return {t.key: t for t in self.tasks}


def _topological_order(specs: list[TaskSpec]) -> list[TaskSpec]:
    by_key = {s.key: s for s in specs}
    indegree: dict[str, int] = {s.key: 0 for s in specs}
    children: dict[str, list[str]] = defaultdict(list)

    for spec in specs:
        for pred_key, _lag in spec.predecessors:
            if pred_key not in by_key:
                raise ValueError(f"Task {spec.key!r} depends on unknown task {pred_key!r}")
            children[pred_key].append(spec.key)
            indegree[spec.key] += 1

    # Stable tie-breaking: stage order, then task order, so output is reproducible.
    ready = deque(
        sorted(
            (k for k, d in indegree.items() if d == 0),
            key=lambda k: (by_key[k].stage_sequence, by_key[k].sequence_order),
        )
    )
    order: list[TaskSpec] = []
    while ready:
        key = ready.popleft()
        order.append(by_key[key])
        newly_ready = []
        for child in children[key]:
            indegree[child] -= 1
            if indegree[child] == 0:
                newly_ready.append(child)
        for child in sorted(newly_ready, key=lambda k: (by_key[k].stage_sequence, by_key[k].sequence_order)):
            ready.append(child)

    if len(order) != len(specs):
        stuck = sorted(set(by_key) - {t.key for t in order})
        raise CyclicDependencyError(f"Cyclic task dependency involving: {', '.join(stuck)}")
    return order


def schedule_project(project_start: date, specs: list[TaskSpec]) -> ProjectSchedule:
    """Compute concrete windows for every task in the project."""
    if not specs:
        raise ValueError("Cannot schedule a project with no tasks")

    scheduled: dict[str, ScheduledTask] = {}

    for spec in _topological_order(specs):
        if spec.predecessors:
            candidates = []
            for pred_key, lag in spec.predecessors:
                pred = scheduled[pred_key]
                candidates.append(spec.calendar.advance(pred.end, 1 + lag))
            earliest = max(candidates)
        else:
            earliest = spec.calendar.next_working_day(project_start)

        if spec.earliest_start and spec.earliest_start > earliest:
            earliest = spec.calendar.next_working_day(spec.earliest_start)

        start, end, dates = spec.calendar.window(earliest, spec.duration)

        # Cumulative day numbering: continue the count from the predecessor chain.
        base = max((scheduled[p].last_day_number for p, _ in spec.predecessors), default=0)
        day_numbers = [base + i for i in range(1, len(dates) + 1)]

        scheduled[spec.key] = ScheduledTask(
            key=spec.key,
            name=spec.name,
            stage_key=spec.stage_key,
            stage_name=spec.stage_name,
            stage_sequence=spec.stage_sequence,
            sequence_order=spec.sequence_order,
            designation=spec.designation,
            duration=spec.duration,
            start=start,
            end=end,
            dates=dates,
            day_numbers=day_numbers,
        )

    tasks = sorted(scheduled.values(), key=lambda t: (t.stage_sequence, t.sequence_order))

    stage_windows: dict[str, tuple[date, date]] = {}
    for task in tasks:
        cur = stage_windows.get(task.stage_key)
        stage_windows[task.stage_key] = (
            min(task.start, cur[0]) if cur else task.start,
            max(task.end, cur[1]) if cur else task.end,
        )

    return ProjectSchedule(
        tasks=tasks,
        stage_windows=stage_windows,
        project_start=min(t.start for t in tasks),
        project_end=max(t.end for t in tasks),
        # Sum of every employee's individual day count -- overlaps are intentionally
        # double-counted, matching the workbook's "Total Man Power Days".
        total_man_days=sum(t.duration for t in tasks),
        # Length of the cumulative chain counter.
        actual_working_days=max(t.last_day_number for t in tasks),
    )
