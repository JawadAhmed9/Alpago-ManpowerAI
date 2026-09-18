# AI Manpower Allocation & Project Scheduling

A scalable manpower allocation and project scheduling system for a design-and-build
joinery company, built against the `TechnicalTest_2.xlsx` brief.

Projects run through eight sequential production stages. Each stage is broken into
named sub-tasks, each needing a specific designation for a number of man-days. The
system converts those into real calendar windows using each employee category's
working calendar, auto-assigns the best available person without ever double-booking
anyone, flags shortages, and renders the whole thing as the Gantt matrix from the
workbook's *Expected Output* sheet — generated dynamically for any project.

The scheduling and allocation logic is **100% deterministic**. The AI layer only turns
already-made decisions into prose, on demand, and is cached. If the LLM provider is
missing or fails, the app degrades to its own deterministic explanations and keeps working.

---

## Quick start

```bash
cp .env.example .env         # optionally add AI_API_KEY
docker compose up -d --build
docker compose run --rm seed # loads the sample workbook data
```

- Web UI: <http://localhost:8080>
- API docs: <http://localhost:8000/docs>
- Health: <http://localhost:8000/health>

Then open **PRJ007 — ABC Renovation Project** and press **Run allocation**.

### Without Docker

```bash
cd backend
pip install -r requirements-dev.txt
export DATABASE_URL="postgresql+psycopg2://alpago:alpago@localhost:5432/alpago"
alembic upgrade head
python -m app.seed.seed
uvicorn app.main:app --reload

cd ../frontend
npm install && npm run dev        # proxies /api to localhost:8000
```

### Tests

```bash
cd backend && DATABASE_URL=sqlite:///./test.db python -m pytest -q
```

190 tests, including a golden regression that asserts every one of PRJ007's fourteen
task windows against the workbook's grid.

---

## What it does

| Requirement | Where |
|---|---|
| CRUD for employees, designations, stages, projects, stage/task definitions | `app/api/routers/`, React CRUD screens |
| Calendar-aware scheduling (weekly offs + admin public holidays) | `app/engine/workcalendar.py`, `app/engine/scheduler.py` |
| Auto-allocation by designation, skill, workload, tenure | `app/engine/allocator.py` |
| Hard constraint: no overlapping allocations per employee, across all projects | `Allocator.allocate` + `BookingIndex`, indexed in the DB |
| Conflict detection (for imported/legacy data) | `GET /api/v1/conflicts` |
| Shortage detection with earliest-free-date recommendation | `Shortage` rows + `GET /api/v1/shortages` |
| Gantt reporting reproducing the Expected Output | `app/services/report_service.py`, `GanttMatrix.jsx` |
| AI explanations + recommendations, on demand and cached | `app/ai/`, `POST /api/v1/projects/{id}/insights` |
| Unlimited employees/projects/stages/designations | nothing is hardcoded to the sample; see ARCHITECTURE.md |

---

## Two findings about the source workbook

Both are documented in detail in [ARCHITECTURE.md](ARCHITECTURE.md), and both are
asserted by the test suite.

**1. The "(Calendar Days)" columns are man-day budgets, not window lengths.**
PRJ007's stage numbers sum to exactly 74, which is the sheet's own *Total Man Power
Days*. Manufacturing's 48 is `15 + 10 + 11 + 12` — the four sub-task durations — yet
that stage spans only ~30 calendar days on the grid because those tasks run in
parallel. The system therefore models the number as a man-day budget that a stage's
tasks partition, and validates that they sum back to it exactly.

**2. The sheet's "Actual Working Days = 51" is off by one; the correct value is 52.**
Its cumulative day counter is self-consistent until *Finishing & polishing*, which
ends at 45 on 24-Oct. *In-line quality inspection* then restarts at 45 instead of 46,
and the slip propagates to the end. Every *date* in the sheet's grid is reproduced
exactly; only this derived total differs, deliberately. (The sheet's Start/End text
columns also contain a few stale values — e.g. Stage 5's header reads
`19-Sep → 23-Sep, 48 days` and Procurement's start reads `13-Sep`, a Sunday. The grid
cells are the trustworthy part and are what the tests assert against.)

---

## API surface

```
GET    /health
GET    /api/v1/dashboard

GET    /api/v1/stages                         POST /api/v1/stages
GET    /api/v1/stages/{id}/designations       POST /api/v1/stages/{id}/designations
GET    /api/v1/designations                   POST /api/v1/designations
GET    /api/v1/calendar-rules                 PATCH /api/v1/calendar-rules/{id}
GET    /api/v1/holidays                       POST/DELETE /api/v1/holidays

GET    /api/v1/employees                      POST /api/v1/employees
GET    /api/v1/employees/{id}                 PATCH/DELETE /api/v1/employees/{id}
GET    /api/v1/employees/{id}/workload

GET    /api/v1/projects                       POST /api/v1/projects
GET    /api/v1/projects/{id}                  PATCH/DELETE /api/v1/projects/{id}
POST   /api/v1/projects/{id}/stages           PATCH /api/v1/projects/{id}/stages/{sid}
GET    /api/v1/projects/{id}/tasks            POST /api/v1/projects/{id}/stages/{sid}/tasks
PATCH  /api/v1/projects/{id}/tasks/{tid}      DELETE /api/v1/projects/{id}/tasks/{tid}
GET    /api/v1/projects/{id}/validate         -- dry run, writes nothing

POST   /api/v1/projects/{id}/allocate         -- schedule + auto-allocate (idempotent)
GET    /api/v1/projects/{id}/allocations
GET    /api/v1/projects/{id}/shortages        GET /api/v1/shortages
GET    /api/v1/conflicts
GET    /api/v1/projects/{id}/gantt            -- the Expected Output view

GET    /api/v1/ai/status
POST   /api/v1/projects/{id}/insights         -- on demand, cached
GET    /api/v1/projects/{id}/insights         -- cache read, never calls the provider
```

---

## Deployment

See [DEPLOY.md](DEPLOY.md). `render.yaml` provisions the API, the static frontend and
a Postgres instance on Render's free tier in one blueprint; `railway.json` covers
Railway.
