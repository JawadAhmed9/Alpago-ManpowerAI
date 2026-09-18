"""Calendar arithmetic. Every expectation is read off the workbook."""

from datetime import date

import pytest

from app.engine.workcalendar import (
    BLUE_COLLAR_WORKDAYS,
    WHITE_COLLAR_WORKDAYS,
    WorkCalendar,
    overlaps,
)

WC = WorkCalendar(WHITE_COLLAR_WORKDAYS, frozenset(), "White Collar")
BC = WorkCalendar(BLUE_COLLAR_WORKDAYS, frozenset(), "Blue Collar")


def test_white_collar_skips_weekend():
    assert WC.is_working_day(date(2026, 9, 4))       # Friday
    assert not WC.is_working_day(date(2026, 9, 5))   # Saturday
    assert not WC.is_working_day(date(2026, 9, 6))   # Sunday


def test_blue_collar_works_saturday_not_sunday():
    assert BC.is_working_day(date(2026, 9, 5))
    assert not BC.is_working_day(date(2026, 9, 6))


@pytest.mark.parametrize(
    ("cal", "start", "duration", "expected_end"),
    [
        (WC, date(2026, 9, 1), 3, date(2026, 9, 3)),    # Concept design
        (WC, date(2026, 9, 3), 2, date(2026, 9, 4)),    # CAD detailing
        (WC, date(2026, 9, 7), 5, date(2026, 9, 11)),   # Planning
        (BC, date(2026, 9, 24), 15, date(2026, 10, 10)),  # Carpentry
        (BC, date(2026, 9, 24), 10, date(2026, 10, 5)),   # CNC
        (BC, date(2026, 10, 6), 11, date(2026, 10, 17)),  # Welding
        (BC, date(2026, 10, 12), 12, date(2026, 10, 24)),  # Finishing
    ],
)
def test_windows_match_expected_output_sheet(cal, start, duration, expected_end):
    assert cal.window(start, duration)[1] == expected_end


def test_advance_crosses_a_weekend_the_successor_does_not_work():
    # QC inspection (Blue Collar) ends Sat 24-Oct; QA sign-off is White Collar,
    # so "one working day later" is Mon 26-Oct, not Tue 27-Oct.
    assert WC.advance(date(2026, 10, 24), 1) == date(2026, 10, 26)


def test_advance_zero_is_same_day_overlap():
    assert WC.advance(date(2026, 9, 3), 0) == date(2026, 9, 3)


def test_public_holiday_pushes_the_window():
    holiday = WorkCalendar(WHITE_COLLAR_WORKDAYS, frozenset({date(2026, 9, 2)}), "WC+hol")
    start, end, days = holiday.window(date(2026, 9, 1), 3)
    assert (start, end) == (date(2026, 9, 1), date(2026, 9, 4))
    assert date(2026, 9, 2) not in days


def test_overlap_is_closed_interval():
    assert overlaps(date(2026, 9, 1), date(2026, 9, 3), date(2026, 9, 3), date(2026, 9, 4))
    assert not overlaps(date(2026, 9, 1), date(2026, 9, 3), date(2026, 9, 4), date(2026, 9, 5))
