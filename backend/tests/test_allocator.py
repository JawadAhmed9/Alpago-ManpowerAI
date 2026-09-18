"""Scoring, the hard overlap constraint, shortages and conflicts."""

from datetime import date

from app.engine.allocator import (
    Allocator,
    Booking,
    BookingIndex,
    Candidate,
    ShortageFinding,
    detect_conflicts,
)


def emp(i, skill="Mid", joined=date(2023, 1, 1), code=None):
    return Candidate(
        employee_id=i,
        employee_code=code or f"EMP{i:03d}",
        name=f"Employee {i}",
        designation_id=1,
        designation="Carpenter",
        skill_level=skill,
        date_of_joining=joined,
    )


def make(candidates, bookings=None):
    return Allocator({1: candidates}, BookingIndex(bookings or []))


def test_prefers_senior_over_mid_over_junior():
    allocator = make([emp(1, "Junior"), emp(2, "Senior"), emp(3, "Mid")])
    decision = allocator.allocate("t1", 1, "Carpenter", date(2026, 9, 1), date(2026, 9, 5))
    assert decision.employee.employee_id == 2


def test_prefers_the_least_loaded_when_skill_is_equal():
    busy = [Booking(1, date(2026, 8, 1), date(2026, 8, 20))]
    allocator = make([emp(1, "Senior"), emp(2, "Senior")], busy)
    decision = allocator.allocate("t1", 1, "Carpenter", date(2026, 9, 1), date(2026, 9, 5))
    assert decision.employee.employee_id == 2


def test_tenure_breaks_a_full_tie():
    allocator = make(
        [emp(1, "Senior", date(2024, 1, 1)), emp(2, "Senior", date(2022, 1, 1))]
    )
    decision = allocator.allocate("t1", 1, "Carpenter", date(2026, 9, 1), date(2026, 9, 5))
    assert decision.employee.employee_id == 2


def test_an_employee_is_never_given_two_overlapping_windows():
    allocator = make([emp(1, "Senior")])
    first = allocator.allocate("t1", 1, "Carpenter", date(2026, 9, 1), date(2026, 9, 10))
    assert not isinstance(first, ShortageFinding)
    # Same person, window overlapping by a single day -> must not be reassigned.
    second = allocator.allocate("t2", 1, "Carpenter", date(2026, 9, 10), date(2026, 9, 15))
    assert isinstance(second, ShortageFinding)
    assert second.eligible_headcount == 1


def test_adjacent_non_overlapping_windows_are_fine():
    allocator = make([emp(1, "Senior")])
    allocator.allocate("t1", 1, "Carpenter", date(2026, 9, 1), date(2026, 9, 10))
    second = allocator.allocate("t2", 1, "Carpenter", date(2026, 9, 11), date(2026, 9, 15))
    assert not isinstance(second, ShortageFinding)


def test_shortage_when_nobody_holds_the_designation():
    allocator = make([])
    finding = allocator.allocate("t1", 1, "Carpenter", date(2026, 9, 1), date(2026, 9, 5))
    assert isinstance(finding, ShortageFinding)
    assert finding.eligible_headcount == 0
    assert "No active employee" in finding.reason()


def test_shortage_reports_when_someone_frees_up():
    busy = [Booking(1, date(2026, 9, 1), date(2026, 9, 20))]
    allocator = make([emp(1, "Senior")], busy)
    finding = allocator.allocate("t1", 1, "Carpenter", date(2026, 9, 5), date(2026, 9, 9))
    assert isinstance(finding, ShortageFinding)
    assert finding.earliest_available_date == date(2026, 9, 21)


def test_inactive_employees_are_not_considered():
    inactive = Candidate(1, "EMP001", "Gone", 1, "Carpenter", "Senior", date(2020, 1, 1), is_active=False)
    finding = make([inactive]).allocate("t1", 1, "Carpenter", date(2026, 9, 1), date(2026, 9, 5))
    assert isinstance(finding, ShortageFinding)


def test_detect_conflicts_finds_imported_double_bookings():
    bookings = [
        Booking(1, date(2026, 9, 1), date(2026, 9, 10), "PRJ001 / A"),
        Booking(1, date(2026, 9, 8), date(2026, 9, 12), "PRJ002 / B"),
        Booking(2, date(2026, 9, 1), date(2026, 9, 10), "PRJ001 / C"),
    ]
    findings = detect_conflicts(bookings, {1: emp(1), 2: emp(2)})
    assert len(findings) == 1
    assert findings[0].overlap_from == date(2026, 9, 8)
    assert findings[0].overlap_to == date(2026, 9, 10)


def test_detect_conflicts_clean_set():
    bookings = [
        Booking(1, date(2026, 9, 1), date(2026, 9, 10), "A"),
        Booking(1, date(2026, 9, 11), date(2026, 9, 12), "B"),
    ]
    assert detect_conflicts(bookings, {1: emp(1)}) == []
