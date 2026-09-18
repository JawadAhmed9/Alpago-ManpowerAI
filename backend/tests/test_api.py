"""End-to-end API tests against a seeded database."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client(seeded_db):
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def prj007_id(client):
    projects = client.get("/api/v1/projects").json()
    return next(p["id"] for p in projects if p["project_code"] == "PRJ007")


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_masters_are_seeded(client):
    assert len(client.get("/api/v1/stages").json()) == 8
    designations = client.get("/api/v1/designations").json()
    assert len(designations) >= 22
    # Project Manager exists but is not an allocatable production role.
    pm = next(d for d in designations if d["name"] == "Project Manager")
    assert pm["allocatable"] is False


def test_calendar_rules(client):
    rules = {r["category"]: r for r in client.get("/api/v1/calendar-rules").json()}
    assert rules["White Collar"]["workdays"] == "1,2,3,4,5"
    assert rules["White Collar"]["overtime_allowed"] is False
    assert rules["Blue Collar"]["workdays"] == "1,2,3,4,5,6"
    assert rules["Blue Collar"]["overtime_allowed"] is True


def test_employee_listing_and_filtering(client):
    assert len(client.get("/api/v1/employees").json()) == 56
    carpenters = client.get("/api/v1/employees", params={"search": "rahul"}).json()
    assert carpenters and all("Rahul" in e["name"] for e in carpenters)


def test_employee_crud_roundtrip(client):
    designation_id = client.get("/api/v1/designations").json()[0]["id"]
    payload = {
        "employee_code": "EMP900",
        "name": "Test Person",
        "designation_id": designation_id,
        "skill_level": "Senior",
        "date_of_joining": "2026-01-01",
    }
    created = client.post("/api/v1/employees", json=payload)
    assert created.status_code == 201
    employee_id = created.json()["id"]

    assert client.post("/api/v1/employees", json=payload).status_code == 409

    patched = client.patch(f"/api/v1/employees/{employee_id}", json={"status": "Inactive"})
    assert patched.json()["status"] == "Inactive"
    assert client.delete(f"/api/v1/employees/{employee_id}").status_code == 204
    assert client.get(f"/api/v1/employees/{employee_id}").status_code == 404


def test_allocate_and_report_prj007(client, prj007_id):
    run = client.post(f"/api/v1/projects/{prj007_id}/allocate").json()
    assert run["summary"]["total_man_days"] == 74
    assert run["summary"]["actual_working_days"] == 52
    assert run["summary"]["shortages"] == 0
    assert run["warnings"] == []
    assert len(run["allocations"]) == 14

    gantt = client.get(f"/api/v1/projects/{prj007_id}/gantt").json()
    assert len(gantt["columns"]) == 61
    assert gantt["summary"]["expected_completion_date"] == "2026-10-31"
    assert all(row["employee"] for row in gantt["rows"] if row["kind"] == "task")


def test_allocation_is_idempotent(client, prj007_id):
    first = client.post(f"/api/v1/projects/{prj007_id}/allocate").json()["summary"]
    second = client.post(f"/api/v1/projects/{prj007_id}/allocate").json()["summary"]
    assert first == second


def test_no_conflicts_after_allocating_every_project(client):
    for project in client.get("/api/v1/projects").json():
        client.post(f"/api/v1/projects/{project['id']}/allocate")
    assert client.get("/api/v1/conflicts").json() == []


def test_holiday_admin_shifts_the_schedule(client, prj007_id):
    before = client.get(f"/api/v1/projects/{prj007_id}/gantt").json()["summary"]
    created = client.post(
        "/api/v1/holidays", json={"holiday_date": "2026-09-02", "label": "Test Holiday"}
    )
    assert created.status_code == 201
    after = client.get(f"/api/v1/projects/{prj007_id}/gantt").json()["summary"]
    assert after["expected_completion_date"] > before["expected_completion_date"]

    assert client.delete(f"/api/v1/holidays/{created.json()['id']}").status_code == 204
    restored = client.get(f"/api/v1/projects/{prj007_id}/gantt").json()["summary"]
    assert restored["expected_completion_date"] == before["expected_completion_date"]


def test_create_project_generates_default_tasks(client):
    payload = {
        "project_code": "PRJ900",
        "name": "API Created Project",
        "start_date": "2026-11-02",
        "priority": "High",
        "stage_budgets": {"Design": 6, "Manufacturing": 20, "Shipping": 3},
    }
    created = client.post("/api/v1/projects", json=payload)
    assert created.status_code == 201
    project = created.json()
    assert len(project["stages"]) == 3

    tasks = client.get(f"/api/v1/projects/{project['id']}/tasks").json()
    assert len(tasks) == 2 + 4 + 2
    assert sum(t["duration_working_days"] for t in tasks) == 6 + 20 + 3

    validation = client.get(f"/api/v1/projects/{project['id']}/validate").json()
    assert validation["ok"] is True

    run = client.post(f"/api/v1/projects/{project['id']}/allocate").json()
    assert run["summary"]["total_man_days"] == 29
    client.delete(f"/api/v1/projects/{project['id']}")


def test_unknown_stage_name_is_rejected(client):
    response = client.post(
        "/api/v1/projects",
        json={
            "project_code": "PRJ901",
            "name": "Bad",
            "start_date": "2026-11-02",
            "stage_budgets": {"Teleportation": 5},
        },
    )
    assert response.status_code == 422
    assert "Teleportation" in response.json()["detail"]


def test_shortage_is_surfaced_when_the_bench_runs_out(client):
    """Hog every Logistics Coordinator, then demand one -- must raise a shortage."""
    designations = {d["name"]: d for d in client.get("/api/v1/designations").json()}
    logistics_id = designations["Logistics Coordinator"]["id"]

    employees = client.get(
        "/api/v1/employees", params={"designation_id": logistics_id}
    ).json()
    for employee in employees:
        client.patch(f"/api/v1/employees/{employee['id']}", json={"status": "Inactive"})

    created = client.post(
        "/api/v1/projects",
        json={
            "project_code": "PRJ902",
            "name": "Shortage Probe",
            "start_date": "2026-12-01",
            "stage_budgets": {"Shipping": 3},
        },
    ).json()
    run = client.post(f"/api/v1/projects/{created['id']}/allocate").json()

    assert run["summary"]["shortages"] == 1
    shortage = run["shortages"][0]
    assert shortage["eligible_headcount"] == 0
    assert "No active employee" in shortage["reason"]

    # Downstream task still scheduled and reported, just unassigned.
    gantt = client.get(f"/api/v1/projects/{created['id']}/gantt").json()
    unassigned = [r for r in gantt["rows"] if r["kind"] == "task" and r["employee"] is None]
    assert len(unassigned) == 1
    assert unassigned[0]["shortage"] is not None

    for employee in employees:
        client.patch(f"/api/v1/employees/{employee['id']}", json={"status": "Active"})
    client.delete(f"/api/v1/projects/{created['id']}")


def test_ai_degrades_gracefully_without_a_key(client, prj007_id):
    status = client.get("/api/v1/ai/status").json()
    assert status["configured"] is False

    generated = client.post(f"/api/v1/projects/{prj007_id}/insights").json()
    assert generated["ai_available"] is False
    assert "unavailable" in generated["note"]
    # Falls back to the deterministic explanation rather than breaking.
    assert len(generated["insights"]) == 14
    assert all(i["model"] == "deterministic" for i in generated["insights"])
    assert all(i["text"] for i in generated["insights"])

    cached = client.get(f"/api/v1/projects/{prj007_id}/insights").json()
    assert cached["source"] == "cache"
    assert len(cached["insights"]) == 14


def test_dashboard(client):
    data = client.get("/api/v1/dashboard").json()
    assert data["projects"] >= 7
    assert data["employees_active"] >= 50
