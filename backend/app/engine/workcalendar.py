"""Working-day arithmetic.

Pure functions over a weekly pattern + a holiday set. No ORM, no I/O, so the
whole thing is trivially unit-testable and reusable from any layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

# ISO weekday numbers
MON, TUE, WED, THU, FRI, SAT, SUN = range(1, 8)

WHITE_COLLAR_WORKDAYS = frozenset({MON, TUE, WED, THU, FRI})
BLUE_COLLAR_WORKDAYS = frozenset({MON, TUE, WED, THU, FRI, SAT})

# Guard against a pathological calendar (e.g. every day a holiday) spinning forever.
MAX_SEARCH_DAYS = 3650


@dataclass(frozen=True)
class WorkCalendar:
    """A weekly working pattern plus admin-configured public holidays."""

    workdays: frozenset[int]
    holidays: frozenset[date] = field(default_factory=frozenset)
    label: str = ""

    def is_working_day(self, day: date) -> bool:
        return day.isoweekday() in self.workdays and day not in self.holidays

    def next_working_day(self, day: date) -> date:
        """First working day on or after ``day``."""
        cursor = day
        for _ in range(MAX_SEARCH_DAYS):
            if self.is_working_day(cursor):
                return cursor
            cursor += timedelta(days=1)
        raise ValueError(f"No working day found within {MAX_SEARCH_DAYS} days of {day} ({self.label})")

    def advance(self, day: date, working_days: int) -> date:
        """Move ``working_days`` working days forward from ``day``.

        ``advance(d, 0)`` == first working day on/after ``d``.
        ``advance(d, 1)`` == the next working day strictly after ``d``.
        """
        if working_days < 0:
            raise ValueError("advance() only moves forward; use a negative lag on the dependency instead")
        if working_days == 0:
            return self.next_working_day(day)
        # Step from the raw calendar date, not from the rolled-forward one: a
        # predecessor may end on a Saturday that the successor's calendar does not
        # work, and "one working day later" must still be the following Monday.
        cursor = day
        for _ in range(working_days):
            cursor = self.next_working_day(cursor + timedelta(days=1))
        return cursor

    def working_days(self, start: date, count: int) -> list[date]:
        """The first ``count`` working days on or after ``start``."""
        if count <= 0:
            raise ValueError("count must be positive")
        out: list[date] = []
        cursor = self.next_working_day(start)
        while True:
            out.append(cursor)
            if len(out) == count:
                return out
            cursor = self.next_working_day(cursor + timedelta(days=1))

    def window(self, start: date, duration: int) -> tuple[date, date, list[date]]:
        """(actual_start, actual_end, all working dates) for a ``duration``-day task."""
        days = self.working_days(start, duration)
        return days[0], days[-1], days

    def count_working_days(self, start: date, end: date) -> int:
        if end < start:
            return 0
        n, cursor = 0, start
        while cursor <= end:
            if self.is_working_day(cursor):
                n += 1
            cursor += timedelta(days=1)
        return n


def calendar_for(workdays_csv: str, holidays: frozenset[date], label: str = "") -> WorkCalendar:
    """Build a calendar from the DB's ``workdays`` column (e.g. ``"1,2,3,4,5"``)."""
    return WorkCalendar(
        workdays=frozenset(int(x) for x in workdays_csv.split(",") if x.strip()),
        holidays=holidays,
        label=label,
    )


def daterange(start: date, end: date) -> list[date]:
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def overlaps(a_start: date, a_end: date, b_start: date, b_end: date) -> bool:
    """Closed-interval overlap test. The hard constraint the allocator enforces."""
    return a_start <= b_end and b_start <= a_end
