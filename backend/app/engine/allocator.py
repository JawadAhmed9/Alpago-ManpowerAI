"""Deterministic allocation engine.

Given scheduled task windows, pick the best available employee for each task.
No LLM involvement: a filter, a scoring function and a hard overlap constraint.

Hard constraint
---------------
One employee is never allocated to two overlapping date ranges, across *any*
project. Enforced here against a live booking index that includes both existing
DB allocations and the ones made earlier in this same run.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

from app.engine.workcalendar import overlaps


@dataclass(frozen=True)
class Candidate:
    """An allocatable employee, flattened out of the ORM."""

    employee_id: int
    employee_code: str
    name: str
    designation_id: int
    designation: str
    skill_level: str
    date_of_joining: date
    is_active: bool = True


@dataclass(frozen=True)
class Booking:
    employee_id: int
    start: date
    end: date
    label: str = ""


@dataclass
class ScoreBreakdown:
    skill: float
    workload: float
    tenure: float
    total: float
    allocated_days_before: int

    def as_dict(self) -> dict:
        return {
            "skill": round(self.skill, 4),
            "workload_penalty": round(self.workload, 4),
            "tenure": round(self.tenure, 6),
            "total": round(self.total, 4),
            "allocated_days_before": self.allocated_days_before,
        }


@dataclass
class AllocationDecision:
    task_key: str
    employee: Candidate
    start: date
    end: date
    working_days: int
    score: float
    breakdown: ScoreBreakdown
    runners_up: list[tuple[str, float]] = field(default_factory=list)

    def reason(self) -> str:
        """Plain-language, fully deterministic explanation.

        The AI layer rewrites this into prose; the system never depends on it.
        """
        return (
            f"{self.employee.name} ({self.employee.employee_code}) - {self.employee.designation}, "
            f"{self.employee.skill_level}. Free for the whole window "
            f"{self.start:%d-%b-%Y} to {self.end:%d-%b-%Y}; "
            f"{self.breakdown.allocated_days_before} day(s) already booked in this horizon."
        )


@dataclass
class ShortageFinding:
    task_key: str
    designation_id: int
    designation: str
    required_from: date
    required_to: date
    eligible_headcount: int
    available_headcount: int
    earliest_available_date: date | None
    blocking: list[tuple[str, date, date]]  # (employee_code, busy_from, busy_to)

    def reason(self) -> str:
        if self.eligible_headcount == 0:
            return (
                f"No active employee holds the designation {self.designation!r}. "
                f"Hire or reassign before {self.required_from:%d-%b-%Y}."
            )
        who = ", ".join(f"{c} (busy {s:%d-%b}-{e:%d-%b})" for c, s, e in self.blocking[:5])
        tail = (
            f" Earliest any of them frees up: {self.earliest_available_date:%d-%b-%Y}."
            if self.earliest_available_date
            else ""
        )
        return (
            f"All {self.eligible_headcount} {self.designation}(s) are already booked across "
            f"{self.required_from:%d-%b-%Y} to {self.required_to:%d-%b-%Y}: {who}.{tail}"
        )


@dataclass
class ConflictFinding:
    employee_id: int
    employee_code: str
    employee_name: str
    left: str
    right: str
    overlap_from: date
    overlap_to: date

    def reason(self) -> str:
        return (
            f"{self.employee_name} ({self.employee_code}) is double-booked on "
            f"{self.left} and {self.right} between {self.overlap_from:%d-%b-%Y} "
            f"and {self.overlap_to:%d-%b-%Y}."
        )


SKILL_ORDER = {"Junior": 0, "Mid": 1, "Senior": 2}


class BookingIndex:
    """In-memory index of who is busy when. Cheap enough for interactive runs."""

    def __init__(self, bookings: list[Booking] | None = None) -> None:
        self._by_employee: dict[int, list[Booking]] = defaultdict(list)
        for booking in bookings or []:
            self._by_employee[booking.employee_id].append(booking)

    def add(self, booking: Booking) -> None:
        self._by_employee[booking.employee_id].append(booking)

    def bookings_for(self, employee_id: int) -> list[Booking]:
        return self._by_employee.get(employee_id, [])

    def is_free(self, employee_id: int, start: date, end: date) -> bool:
        return not any(overlaps(start, end, b.start, b.end) for b in self.bookings_for(employee_id))

    def conflicting(self, employee_id: int, start: date, end: date) -> list[Booking]:
        return [b for b in self.bookings_for(employee_id) if overlaps(start, end, b.start, b.end)]

    def allocated_days(self, employee_id: int) -> int:
        return sum((b.end - b.start).days + 1 for b in self.bookings_for(employee_id))

    def earliest_free_after(self, employee_id: int, start: date, end: date) -> date:
        """First date on/after ``start`` where a window of the same length fits."""
        span = (end - start).days
        cursor = start
        for _ in range(730):
            blockers = self.conflicting(employee_id, cursor, cursor + timedelta(days=span))
            if not blockers:
                return cursor
            cursor = max(b.end for b in blockers) + timedelta(days=1)
        return cursor


class Allocator:
    """Filter -> availability check -> score -> assign."""

    def __init__(
        self,
        candidates_by_designation: dict[int, list[Candidate]],
        booking_index: BookingIndex,
        *,
        skill_weights: dict[str, float] | None = None,
        workload_penalty_per_day: float = 0.15,
    ) -> None:
        self._candidates = candidates_by_designation
        self.bookings = booking_index
        self._skill_weights = skill_weights or {"Senior": 3.0, "Mid": 2.0, "Junior": 1.0}
        self._workload_penalty = workload_penalty_per_day

    # -- scoring ---------------------------------------------------------
    def score(self, candidate: Candidate) -> ScoreBreakdown:
        skill = self._skill_weights.get(candidate.skill_level, 1.0)
        allocated = self.bookings.allocated_days(candidate.employee_id)
        workload = -self._workload_penalty * allocated
        # Earlier joiner wins ties. Scaled tiny so it never outranks skill/workload.
        tenure = -candidate.date_of_joining.toordinal() * 1e-7
        return ScoreBreakdown(
            skill=skill,
            workload=workload,
            tenure=tenure,
            total=skill + workload + tenure,
            allocated_days_before=allocated,
        )

    # -- main entry point ------------------------------------------------
    def allocate(
        self, task_key: str, designation_id: int, designation_name: str, start: date, end: date
    ) -> AllocationDecision | ShortageFinding:
        eligible = [c for c in self._candidates.get(designation_id, []) if c.is_active]
        available = [c for c in eligible if self.bookings.is_free(c.employee_id, start, end)]

        if not available:
            blocking: list[tuple[str, date, date]] = []
            earliest: date | None = None
            for candidate in eligible:
                for booking in self.bookings.conflicting(candidate.employee_id, start, end):
                    blocking.append((candidate.employee_code, booking.start, booking.end))
                free_at = self.bookings.earliest_free_after(candidate.employee_id, start, end)
                earliest = free_at if earliest is None else min(earliest, free_at)
            return ShortageFinding(
                task_key=task_key,
                designation_id=designation_id,
                designation=designation_name,
                required_from=start,
                required_to=end,
                eligible_headcount=len(eligible),
                available_headcount=0,
                earliest_available_date=earliest,
                blocking=sorted(blocking, key=lambda b: (b[1], b[0])),
            )

        ranked = sorted(
            ((c, self.score(c)) for c in available),
            key=lambda pair: (
                -pair[1].total,
                -SKILL_ORDER.get(pair[0].skill_level, 0),
                pair[0].date_of_joining,
                pair[0].employee_code,
            ),
        )
        winner, breakdown = ranked[0]
        self.bookings.add(Booking(winner.employee_id, start, end, label=task_key))

        return AllocationDecision(
            task_key=task_key,
            employee=winner,
            start=start,
            end=end,
            working_days=0,  # filled in by the caller, which knows the calendar
            score=breakdown.total,
            breakdown=breakdown,
            runners_up=[(c.employee_code, round(b.total, 3)) for c, b in ranked[1:4]],
        )


def detect_conflicts(
    bookings: list[Booking], employees: dict[int, Candidate], labels: dict[str, str] | None = None
) -> list[ConflictFinding]:
    """Find existing double-bookings.

    Should return [] for anything this system allocated, but legacy or imported
    rows can violate the rule -- so it stays queryable as a first-class check.
    """
    labels = labels or {}
    by_employee: dict[int, list[Booking]] = defaultdict(list)
    for booking in bookings:
        by_employee[booking.employee_id].append(booking)

    findings: list[ConflictFinding] = []
    for employee_id, items in by_employee.items():
        items.sort(key=lambda b: (b.start, b.end))
        for i, left in enumerate(items):
            for right in items[i + 1 :]:
                if right.start > left.end:
                    break  # sorted, so nothing further can overlap
                employee = employees.get(employee_id)
                findings.append(
                    ConflictFinding(
                        employee_id=employee_id,
                        employee_code=employee.employee_code if employee else str(employee_id),
                        employee_name=employee.name if employee else "Unknown",
                        left=labels.get(left.label, left.label),
                        right=labels.get(right.label, right.label),
                        overlap_from=max(left.start, right.start),
                        overlap_to=min(left.end, right.end),
                    )
                )
    return findings
