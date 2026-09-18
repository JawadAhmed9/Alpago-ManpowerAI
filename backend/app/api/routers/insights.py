from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.client import is_configured
from app.ai.insights import generate_insights
from app.db import get_db
from app.models import AIInsight, Project
from app.schemas import InsightRunOut

router = APIRouter(tags=["ai"])


@router.get("/ai/status")
def ai_status():
    from app.config import settings

    return {
        "enabled": settings.ai_enabled,
        "configured": is_configured(),
        "provider": settings.ai_provider,
        "model": settings.ai_model,
    }


@router.post("/projects/{project_id}/insights", response_model=InsightRunOut)
def create_insights(
    project_id: int,
    force: bool = Query(False, description="Regenerate even if cached insights exist"),
    db: Session = Depends(get_db),
):
    """On-demand only. Results are cached; page loads never hit the provider."""
    if not db.get(Project, project_id):
        raise HTTPException(404, "Project not found")
    return generate_insights(db, project_id, force=force)


@router.get("/projects/{project_id}/insights", response_model=InsightRunOut)
def read_insights(project_id: int, db: Session = Depends(get_db)):
    """Read cached insights. Never calls the provider."""
    if not db.get(Project, project_id):
        raise HTTPException(404, "Project not found")
    rows = db.scalars(select(AIInsight).where(AIInsight.project_id == project_id)).all()
    return {
        "project_id": project_id,
        "source": "cache" if rows else "empty",
        "ai_available": is_configured(),
        "note": None if rows else "No insights generated yet. Use 'Generate AI Insights'.",
        "insights": [
            {
                "id": r.id,
                "related_type": r.related_type.value,
                "related_id": r.related_id,
                "text": r.text,
                "model": r.model,
                "generated_at": r.generated_at,
            }
            for r in rows
        ],
    }
