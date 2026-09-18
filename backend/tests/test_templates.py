import pytest

from app.seed.templates import DEFAULT_STAGE_TEMPLATES, split_budget


def weights(stage: str) -> list[float]:
    return [t.weight for t in DEFAULT_STAGE_TEMPLATES[stage].tasks]


@pytest.mark.parametrize(
    ("stage", "budget", "expected"),
    [
        ("Design", 5, [3, 2]),
        ("Manufacturing", 48, [15, 10, 11, 12]),
        ("Quality Control", 2, [1, 1]),
        ("Shipping", 3, [1, 2]),
    ],
)
def test_prj007_splits_reproduce_the_sheet(stage, budget, expected):
    assert split_budget(budget, weights(stage)) == expected


@pytest.mark.parametrize("budget", range(4, 120))
def test_split_always_sums_back_to_budget(budget):
    parts = split_budget(budget, weights("Manufacturing"))
    assert sum(parts) == budget
    assert min(parts) >= 1


def test_budget_too_small_for_the_task_count_is_rejected():
    with pytest.raises(ValueError, match="cannot cover"):
        split_budget(3, weights("Manufacturing"))


def test_quality_control_exits_through_inspection_not_qa_signoff():
    # Packing follows the in-line inspection; QA sign-off runs in parallel.
    assert DEFAULT_STAGE_TEMPLATES["Quality Control"].resolved_exits() == (0,)
