"""Default sub-task templates per stage.

The workbook never defines this breakdown as master data -- it only appears once,
inside the PRJ007 worked example. So the system models tasks as first-class rows a
project manager can edit, and ships these templates so a new project is usable
immediately.

A template splits the stage's man-day budget across tasks by ``weight`` using the
largest-remainder method, so the task durations always sum back to the budget
exactly, at any project size. For PRJ007 the weights reproduce the workbook's
numbers precisely (Design 5 -> 3+2, Manufacturing 48 -> 15+10+11+12, and so on).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TaskTemplate:
    name: str
    designation: str
    weight: float
    # Indices (within this stage) this task waits on, with a working-day lag.
    # lag == -1 means "start on the predecessor's final day" (one-day overlap).
    predecessors: tuple[tuple[int, int], ...] = ()


@dataclass(frozen=True)
class StageTemplate:
    stage: str
    tasks: tuple[TaskTemplate, ...]
    # Lag applied to the edge coming in from the previous stage.
    entry_lag: int = 0
    # Which task indices the NEXT stage should hang off. Defaults to the stage's
    # terminal tasks. Quality Control overrides it: packing follows the in-line
    # inspection, not the parallel QA sign-off.
    exit_task_indices: tuple[int, ...] = ()

    def resolved_exits(self) -> tuple[int, ...]:
        if self.exit_task_indices:
            return self.exit_task_indices
        has_successor = {p for t in self.tasks for p, _ in t.predecessors}
        return tuple(i for i in range(len(self.tasks)) if i not in has_successor)


DEFAULT_STAGE_TEMPLATES: dict[str, StageTemplate] = {
    "Design": StageTemplate(
        stage="Design",
        tasks=(
            TaskTemplate("Concept design & drawings", "Design Engineer", 3 / 5),
            TaskTemplate("CAD detailing & shop drawings", "CAD Draftsman", 2 / 5, ((0, -1),)),
        ),
    ),
    "Planning": StageTemplate(
        stage="Planning",
        tasks=(TaskTemplate("Production planning & scheduling", "Project Planner / Scheduler", 1.0),),
    ),
    "Procurement": StageTemplate(
        stage="Procurement",
        tasks=(TaskTemplate("Material & BOQ procurement", "Procurement Officer", 1.0),),
    ),
    "Sourcing": StageTemplate(
        stage="Sourcing",
        tasks=(TaskTemplate("Vendor & supplier sourcing", "Vendor Development Executive", 1.0),),
    ),
    "Manufacturing": StageTemplate(
        stage="Manufacturing",
        tasks=(
            TaskTemplate("Carpentry & assembly", "Carpenter", 15 / 48),
            TaskTemplate("CNC cutting & edge banding", "Machine Operator (CNC/Edge Band)", 10 / 48),
            TaskTemplate("Welding & metal fabrication", "Welder / Fabricator", 11 / 48, ((1, 0),)),
            TaskTemplate("Finishing & polishing", "Finishing / Polishing Technician", 12 / 48, ((0, 0),)),
        ),
    ),
    "Quality Control": StageTemplate(
        stage="Quality Control",
        tasks=(
            TaskTemplate("In-line quality inspection", "QC Inspector", 0.5),
            TaskTemplate("Final QA sign-off", "QA Engineer", 0.5, ((0, 0),)),
        ),
        # Inspection runs in-line, overlapping the last production day.
        entry_lag=-1,
        # Packing follows inspection; the QA sign-off is parallel paperwork.
        exit_task_indices=(0,),
    ),
    "Packing": StageTemplate(
        stage="Packing",
        tasks=(TaskTemplate("Packing & crating", "Packing Helper", 1.0),),
    ),
    "Shipping": StageTemplate(
        stage="Shipping",
        tasks=(
            TaskTemplate("Dispatch coordination", "Logistics Coordinator", 1 / 3),
            TaskTemplate("Loading & transport", "Driver", 2 / 3, ((0, 0),)),
        ),
    ),
}


def split_budget(budget: int, weights: list[float], minimum: int = 1) -> list[int]:
    """Largest-remainder split so the parts always sum to ``budget`` exactly."""
    n = len(weights)
    if n == 0:
        return []
    if budget < n * minimum:
        raise ValueError(
            f"Stage budget of {budget} man-day(s) cannot cover {n} task(s) at a minimum of {minimum} each"
        )
    total_weight = sum(weights) or float(n)
    spare = budget - n * minimum
    raw = [w / total_weight * spare for w in weights]
    parts = [minimum + int(x) for x in raw]
    remainders = sorted(range(n), key=lambda i: (-(raw[i] - int(raw[i])), i))
    for i in range(budget - sum(parts)):
        parts[remainders[i % n]] += 1
    return parts
