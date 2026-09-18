"""Generate and cache natural-language insights for an allocation run.

Contract:
  * triggered on demand only (POST /projects/{id}/insights), never on page load;
  * results are cached in ai_insights and re-served until regenerated;
  * one provider call per run (batched), capped by AI_MAX_ITEMS_PER_RUN;
  * if the provider is unavailable, the deterministic explanation is stored
    instead and the response says so -- the app never breaks on a missing key.
"""

from __future__ import annotations

import json
import re

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.ai.client import AIUnavailable, complete, is_configured
from app.config import settings
from app.models import (
    AIInsight,
    Allocation,
    Employee,
    InsightType,
    Project,
    ProjectStage,
    Shortage,
    Task,
)


def _allocation_facts(db: Session, project_id: int) -> list[dict]:
    rows = db.execute(
        select(Allocation, Task.name, Employee)
        .join(Task, Allocation.task_id == Task.id)
        .join(ProjectStage, Task.project_stage_id == ProjectStage.id)
        .join(Employee, Allocation.employee_id == Employee.id)
        .where(ProjectStage.project_id == project_id)
        .order_by(ProjectStage.sequence_order, Task.sequence_order)
    ).all()

    facts = []
    for allocation, task_name, employee in rows:
        breakdown = json.loads(allocation.score_breakdown or "{}")
        facts.append(
            {
                "id": allocation.id,
                "task": task_name,
                "employee": f"{employee.name} ({employee.employee_code})",
                "designation": employee.designation.name,
                "skill": employee.skill_level.value,
                "window": f"{allocation.actual_start_date:%d-%b-%Y} to {allocation.actual_end_date:%d-%b-%Y}",
                "days": allocation.working_days,
                "already_booked_days": breakdown.get("allocated_days_before", 0),
                "deterministic_reason": breakdown.get("reason", ""),
            }
        )
    return facts


def _shortage_facts(db: Session, project_id: int) -> list[dict]:
    rows = db.execute(
        select(Shortage, Task.name)
        .join(Task, Shortage.task_id == Task.id)
        .where(Shortage.project_id == project_id)
    ).all()
    return [
        {
            "id": shortage.id,
            "task": task_name,
            "designation": shortage.designation.name,
            "window": f"{shortage.required_from:%d-%b-%Y} to {shortage.required_to:%d-%b-%Y}",
            "eligible_headcount": shortage.eligible_headcount,
            "earliest_available": (
                f"{shortage.earliest_available_date:%d-%b-%Y}"
                if shortage.earliest_available_date
                else "unknown"
            ),
            "deterministic_reason": shortage.reason,
        }
        for shortage, task_name in rows
    ]


def _build_prompt(project: Project, allocations: list[dict], shortages: list[dict]) -> str:
    lines = [
        f"Project {project.project_code} - {project.name}.",
        "",
        "ALLOCATIONS (explain each pick in one sentence, prefix with its id):",
    ]
    for item in allocations:
        lines.append(
            f"[A{item['id']}] task={item['task']!r}; assigned={item['employee']}; "
            f"role={item['designation']}; skill={item['skill']}; dates={item['window']}; "
            f"duration={item['days']} working days; "
            f"days already booked elsewhere={item['already_booked_days']}"
        )
    if shortages:
        lines += ["", "SHORTAGES (one sentence each with a concrete recommendation, prefix with its id):"]
        for item in shortages:
            lines.append(
                f"[S{item['id']}] task={item['task']!r}; role needed={item['designation']}; "
                f"dates={item['window']}; eligible headcount={item['eligible_headcount']}; "
                f"earliest anyone frees up={item['earliest_available']}"
            )
    lines += [
        "",
        "Output one line per id, formatted exactly as: [A12] sentence",
        "Do not add any other text.",
    ]
    return "\n".join(lines)


def _parse(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        match = re.match(r"^\s*\[?([AS]\d+)\]?[:\s-]+(.+)$", line.strip())
        if match:
            out[match.group(1)] = match.group(2).strip()
    return out


def generate_insights(db: Session, project_id: int, force: bool = False) -> dict:
    """Generate (or re-serve) insights for a project's latest allocation run."""
    project = db.get(Project, project_id)
    if project is None:
        raise ValueError(f"Project {project_id} not found")

    cached = db.scalars(select(AIInsight).where(AIInsight.project_id == project_id)).all()
    if cached and not force:
        return {
            "project_id": project_id,
            "source": "cache",
            "ai_available": True,
            "insights": [_serialise(i) for i in cached],
        }

    allocations = _allocation_facts(db, project_id)
    shortages = _shortage_facts(db, project_id)
    if not allocations and not shortages:
        return {"project_id": project_id, "source": "empty", "ai_available": is_configured(), "insights": []}

    cap = settings.ai_max_items_per_run
    capped_allocations, capped_shortages = allocations[:cap], shortages[:cap]

    generated: dict[str, str] = {}
    ai_available = False
    note = None
    if is_configured():
        try:
            generated = _parse(
                complete(_build_prompt(project, capped_allocations, capped_shortages))
            )
            ai_available = True
        except AIUnavailable as exc:
            note = f"AI insight unavailable ({exc}). Showing the deterministic explanation instead."
    else:
        note = (
            "AI insight unavailable (no provider configured). "
            "Showing the deterministic explanation instead."
        )

    db.execute(delete(AIInsight).where(AIInsight.project_id == project_id))

    rows: list[AIInsight] = []
    for item in allocations:
        rows.append(
            AIInsight(
                related_type=InsightType.ALLOCATION,
                related_id=item["id"],
                project_id=project_id,
                text=generated.get(f"A{item['id']}") or item["deterministic_reason"],
                model=settings.ai_model if ai_available else "deterministic",
            )
        )
    for item in shortages:
        rows.append(
            AIInsight(
                related_type=InsightType.SHORTAGE,
                related_id=item["id"],
                project_id=project_id,
                text=generated.get(f"S{item['id']}") or item["deterministic_reason"],
                model=settings.ai_model if ai_available else "deterministic",
            )
        )
    db.add_all(rows)
    db.flush()

    return {
        "project_id": project_id,
        "source": "generated",
        "ai_available": ai_available,
        "note": note,
        "insights": [_serialise(r) for r in rows],
    }


def _serialise(insight: AIInsight) -> dict:
    return {
        "id": insight.id,
        "related_type": insight.related_type.value,
        "related_id": insight.related_id,
        "text": insight.text,
        "model": insight.model,
        "generated_at": insight.generated_at.isoformat() if insight.generated_at else None,
    }
