"""Stages, designations, calendar rules and public holidays."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import CalendarRule, Designation, PublicHoliday, Stage, StageDesignation
from app.schemas import (
    CalendarRuleOut,
    CalendarRuleUpdate,
    DesignationIn,
    DesignationOut,
    DesignationUpdate,
    HolidayIn,
    HolidayOut,
    StageDesignationIn,
    StageIn,
    StageOut,
    StageUpdate,
)

router = APIRouter(tags=["masters"])


# --- stages ----------------------------------------------------------------
@router.get("/stages", response_model=list[StageOut])
def list_stages(db: Session = Depends(get_db)):
    return db.scalars(select(Stage).order_by(Stage.sequence_order)).all()


@router.post("/stages", response_model=StageOut, status_code=status.HTTP_201_CREATED)
def create_stage(payload: StageIn, db: Session = Depends(get_db)):
    stage = Stage(**payload.model_dump())
    db.add(stage)
    try:
        db.flush()
    except IntegrityError as exc:
        raise HTTPException(409, "A stage with that name or sequence already exists") from exc
    return stage


@router.patch("/stages/{stage_id}", response_model=StageOut)
def update_stage(stage_id: int, payload: StageUpdate, db: Session = Depends(get_db)):
    stage = db.get(Stage, stage_id)
    if stage is None:
        raise HTTPException(404, "Stage not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(stage, field, value)
    try:
        db.flush()
    except IntegrityError as exc:
        raise HTTPException(409, "A stage with that name or sequence already exists") from exc
    return stage


@router.get("/stages/{stage_id}/designations", response_model=list[DesignationOut])
def stage_designations(stage_id: int, db: Session = Depends(get_db)):
    return db.scalars(
        select(Designation)
        .join(StageDesignation, StageDesignation.designation_id == Designation.id)
        .where(StageDesignation.stage_id == stage_id)
        .order_by(Designation.name)
    ).all()


@router.post("/stages/{stage_id}/designations", status_code=status.HTTP_201_CREATED)
def link_designation(stage_id: int, payload: StageDesignationIn, db: Session = Depends(get_db)):
    if not db.get(Stage, stage_id):
        raise HTTPException(404, "Stage not found")
    if not db.get(Designation, payload.designation_id):
        raise HTTPException(404, "Designation not found")
    db.add(StageDesignation(stage_id=stage_id, designation_id=payload.designation_id))
    try:
        db.flush()
    except IntegrityError as exc:
        raise HTTPException(409, "Already linked") from exc
    return {"stage_id": stage_id, "designation_id": payload.designation_id}


# --- designations ----------------------------------------------------------
@router.get("/designations", response_model=list[DesignationOut])
def list_designations(db: Session = Depends(get_db)):
    return db.scalars(select(Designation).order_by(Designation.name)).all()


@router.post("/designations", response_model=DesignationOut, status_code=status.HTTP_201_CREATED)
def create_designation(payload: DesignationIn, db: Session = Depends(get_db)):
    designation = Designation(**payload.model_dump())
    db.add(designation)
    try:
        db.flush()
    except IntegrityError as exc:
        raise HTTPException(409, "A designation with that name already exists") from exc
    return designation


@router.patch("/designations/{designation_id}", response_model=DesignationOut)
def update_designation(designation_id: int, payload: DesignationUpdate, db: Session = Depends(get_db)):
    designation = db.get(Designation, designation_id)
    if designation is None:
        raise HTTPException(404, "Designation not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(designation, field, value)
    try:
        db.flush()
    except IntegrityError as exc:
        raise HTTPException(409, "A designation with that name already exists") from exc
    return designation


# --- calendar rules --------------------------------------------------------
@router.get("/calendar-rules", response_model=list[CalendarRuleOut])
def list_calendar_rules(db: Session = Depends(get_db)):
    return db.scalars(select(CalendarRule)).all()


@router.patch("/calendar-rules/{rule_id}", response_model=CalendarRuleOut)
def update_calendar_rule(rule_id: int, payload: CalendarRuleUpdate, db: Session = Depends(get_db)):
    rule = db.get(CalendarRule, rule_id)
    if rule is None:
        raise HTTPException(404, "Calendar rule not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)
    db.flush()
    return rule


# --- public holidays -------------------------------------------------------
@router.get("/holidays", response_model=list[HolidayOut])
def list_holidays(db: Session = Depends(get_db)):
    return db.scalars(select(PublicHoliday).order_by(PublicHoliday.holiday_date)).all()


@router.post("/holidays", response_model=HolidayOut, status_code=status.HTTP_201_CREATED)
def create_holiday(payload: HolidayIn, db: Session = Depends(get_db)):
    holiday = PublicHoliday(**payload.model_dump())
    db.add(holiday)
    try:
        db.flush()
    except IntegrityError as exc:
        raise HTTPException(409, "That date is already a public holiday") from exc
    return holiday


@router.delete("/holidays/{holiday_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_holiday(holiday_id: int, db: Session = Depends(get_db)):
    holiday = db.get(PublicHoliday, holiday_id)
    if holiday is None:
        raise HTTPException(404, "Public holiday not found")
    db.delete(holiday)
