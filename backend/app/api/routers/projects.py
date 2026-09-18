from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models import (
    Designation,
    Project,
    ProjectStage,
    Stage,
    Task,
    TaskDependency,
)
from app.schemas import (
    ProjectDetailOut,
    ProjectIn,
    ProjectOut,
    ProjectStageIn,
    ProjectStageOut,
    ProjectUpdate,
    TaskIn,
    TaskOut,
    TaskUpdate,
)
from app.seed.seed import generate_tasks_from_templates
from app.services.scheduling_service import compute_schedule, validate_stage_budgets

router = APIRouter(prefix="/projects", tags=["projects"])


def _load(db: Session, project_id: int) -> Project:
    project = db.scalars(
        select(Project)
        .options(
            selectinload(Project.stages).selectinload(ProjectStage.tasks),
            selectinload(Project.stages).selectinload(ProjectStage.stage),
        )
        .where(Project.id == project_id)
    ).first()
    if project is None:
        raise HTTPException(404, "Project not found")
    return project


@router.get("", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    return db.scalars(select(Project).order_by(Project.project_code)).all()


@router.post("", response_model=ProjectDetailOut, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectIn, db: Session = Depends(get_db)):
    """Create a project and, if stage budgets are supplied, its default task breakdown."""
    data = payload.model_dump()
    budgets = data.pop("stage_budgets")
    project = Project(**data)
    db.add(project)
    try:
        db.flush()
    except IntegrityError as exc:
        raise HTTPException(409, f"Project code {payload.project_code} already exists") from exc

    if budgets:
        stages = {s.name: s for s in db.scalars(select(Stage)).all()}
        unknown = sorted(set(budgets) - set(stages))
        if unknown:
            raise HTTPException(422, f"Unknown stage(s): {', '.join(unknown)}")
        for name, budget in budgets.items():
            stage = stages[name]
            db.add(
                ProjectStage(
                    project_id=project.id,
                    stage_id=stage.id,
                    sequence_order=stage.sequence_order,
                    man_days_budgeted=int(budget),
                )
            )
        db.flush()
        designations = {d.name: d for d in db.scalars(select(Designation)).all()}
        try:
            generate_tasks_from_templates(db, project, designations)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    db.flush()
    return _load(db, project.id)


@router.get("/{project_id}", response_model=ProjectDetailOut)
def get_project(project_id: int, db: Session = Depends(get_db)):
    return _load(db, project_id)


@router.patch("/{project_id}", response_model=ProjectDetailOut)
def update_project(project_id: int, payload: ProjectUpdate, db: Session = Depends(get_db)):
    project = _load(db, project_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    db.flush()
    return _load(db, project_id)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int, db: Session = Depends(get_db)):
    db.delete(_load(db, project_id))


# --- stages within a project ----------------------------------------------
@router.post("/{project_id}/stages", response_model=ProjectStageOut, status_code=status.HTTP_201_CREATED)
def add_stage(project_id: int, payload: ProjectStageIn, db: Session = Depends(get_db)):
    _load(db, project_id)
    stage = db.get(Stage, payload.stage_id)
    if stage is None:
        raise HTTPException(404, "Stage not found")
    project_stage = ProjectStage(
        project_id=project_id,
        stage_id=stage.id,
        sequence_order=stage.sequence_order,
        man_days_budgeted=payload.man_days_budgeted,
    )
    db.add(project_stage)
    try:
        db.flush()
    except IntegrityError as exc:
        raise HTTPException(409, "That stage is already on this project") from exc
    return project_stage


@router.patch("/{project_id}/stages/{stage_id}", response_model=ProjectStageOut)
def update_stage_budget(
    project_id: int, stage_id: int, payload: ProjectStageIn, db: Session = Depends(get_db)
):
    project_stage = db.get(ProjectStage, stage_id)
    if project_stage is None or project_stage.project_id != project_id:
        raise HTTPException(404, "Project stage not found")
    project_stage.man_days_budgeted = payload.man_days_budgeted
    db.flush()
    return project_stage


# --- tasks -----------------------------------------------------------------
@router.get("/{project_id}/tasks", response_model=list[TaskOut])
def list_tasks(project_id: int, db: Session = Depends(get_db)):
    return db.scalars(
        select(Task)
        .join(ProjectStage, Task.project_stage_id == ProjectStage.id)
        .where(ProjectStage.project_id == project_id)
        .order_by(ProjectStage.sequence_order, Task.sequence_order)
    ).all()


@router.post(
    "/{project_id}/stages/{stage_id}/tasks", response_model=TaskOut, status_code=status.HTTP_201_CREATED
)
def create_task(project_id: int, stage_id: int, payload: TaskIn, db: Session = Depends(get_db)):
    project_stage = db.get(ProjectStage, stage_id)
    if project_stage is None or project_stage.project_id != project_id:
        raise HTTPException(404, "Project stage not found")
    if not db.get(Designation, payload.designation_id):
        raise HTTPException(404, "Designation not found")

    data = payload.model_dump()
    predecessor_ids = data.pop("predecessor_ids")
    lag = data.pop("lag_days")
    task = Task(project_stage_id=stage_id, **data)
    db.add(task)
    db.flush()

    for predecessor_id in predecessor_ids:
        if not db.get(Task, predecessor_id):
            raise HTTPException(404, f"Predecessor task {predecessor_id} not found")
        db.add(TaskDependency(predecessor_id=predecessor_id, successor_id=task.id, lag_days=lag))
    db.flush()
    return task


@router.patch("/{project_id}/tasks/{task_id}", response_model=TaskOut)
def update_task(project_id: int, task_id: int, payload: TaskUpdate, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if task is None or task.project_stage.project_id != project_id:
        raise HTTPException(404, "Task not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    db.flush()
    return task


@router.delete("/{project_id}/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(project_id: int, task_id: int, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if task is None or task.project_stage.project_id != project_id:
        raise HTTPException(404, "Task not found")
    db.delete(task)


@router.get("/{project_id}/validate")
def validate_project(project_id: int, db: Session = Depends(get_db)):
    """Dry-run: budget checks plus a schedule preview, without writing anything."""
    project = _load(db, project_id)
    warnings = validate_stage_budgets(project)
    try:
        _, schedule = compute_schedule(db, project_id, persist=False)
    except ValueError as exc:
        return {"ok": False, "warnings": warnings, "error": str(exc)}
    return {
        "ok": not warnings,
        "warnings": warnings,
        "preview": {
            "project_start": schedule.project_start,
            "project_end": schedule.project_end,
            "total_man_days": schedule.total_man_days,
            "actual_working_days": schedule.actual_working_days,
            "tasks": len(schedule.tasks),
        },
    }
