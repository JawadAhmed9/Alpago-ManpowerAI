import os
import tempfile

import pytest

# Point the app at a throwaway sqlite file BEFORE app.config is imported.
_TMP = tempfile.mkdtemp(prefix="alpago-test-")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TMP}/test.db")
os.environ.setdefault("AI_ENABLED", "false")


@pytest.fixture(scope="session")
def seeded_db():
    from app.db import SessionLocal
    from app.seed import seed

    seed.run(reset=True)
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture(scope="session")
def prj007(seeded_db):
    from sqlalchemy import select

    from app.models import Project

    return seeded_db.scalar(select(Project.id).where(Project.project_code == "PRJ007"))
