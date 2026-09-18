import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import allocation, employees, insights, masters, projects, reports
from app.config import settings
from app.db import Base, engine

logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def lifespan(_: FastAPI):
    # Alembic owns the schema in production; this makes a bare container usable.
    Base.metadata.create_all(engine)
    yield


app = FastAPI(
    lifespan=lifespan,
    title=settings.app_name,
    version="1.0.0",
    description=(
        "Deterministic manpower allocation and project scheduling, with a thin, "
        "cached AI explanation layer. Scheduling and allocation never depend on the LLM."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API = "/api/v1"
for included in (
    masters.router,
    employees.router,
    projects.router,
    allocation.router,
    reports.router,
    insights.router,
):
    app.include_router(included, prefix=API)


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.app_name, "environment": settings.environment}
