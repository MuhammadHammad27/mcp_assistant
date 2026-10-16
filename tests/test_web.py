from fastapi.testclient import TestClient

from agency_ops import server, web
from agency_ops.database import AgencyStore


def use_temp_store(tmp_path, monkeypatch):
    temp_store = AgencyStore(tmp_path / "agency.db")
    temp_store.initialize()
    monkeypatch.setattr(server, "store", temp_store)
    monkeypatch.setattr(web, "store", temp_store)
    return temp_store


def test_dashboard_api_creates_full_workspace(tmp_path, monkeypatch):
    use_temp_store(tmp_path, monkeypatch)
    client = TestClient(web.app)

    create_project = client.post(
        "/api/projects",
        json={
            "client_name": "Northstar Labs",
            "project_name": "Brand Refresh",
            "brief": "Create a focused brand refresh for a new B2B developer product.",
            "timeline_days": 10,
        },
    )
    assert create_project.status_code == 201
    project = create_project.json()["project"]

    starter_tasks = client.post(f"/api/projects/{project['id']}/starter-tasks")
    assert starter_tasks.status_code == 201
    assert starter_tasks.json()["count"] == 3

    duplicate_starter_tasks = client.post(f"/api/projects/{project['id']}/starter-tasks")
    assert duplicate_starter_tasks.status_code == 422

    task_list = client.get(f"/api/projects/{project['id']}/tasks")
    assert task_list.status_code == 200
    assert len(task_list.json()["tasks"]) == 3

    status_update = client.patch(f"/api/tasks/{task_list.json()['tasks'][0]['id']}", json={"status": "in_progress"})
    assert status_update.status_code == 200
    assert status_update.json()["task"]["status"] == "in_progress"
    board_tasks = client.get("/api/tasks")
    assert board_tasks.status_code == 200
    assert len(board_tasks.json()["tasks"]) == 3
    proposal = client.post(f"/api/projects/{project['id']}/proposal", json={"scope": "Strategy, design and final handoff.", "timeline": "10 days", "investment_note": "To be agreed"})
    assert proposal.status_code == 201
    saved_proposal = proposal.json()["proposal"]
    assert "Brand Refresh" in saved_proposal["content"]

    export = client.get(f"/api/proposals/{saved_proposal['id']}/export.pdf")
    assert export.status_code == 200
    assert export.headers["content-type"].startswith("application/pdf")
    assert export.content.startswith(b"%PDF")

    dashboard = client.get("/api/dashboard")
    assert dashboard.status_code == 200
    assert dashboard.json()["project_count"] == 1
    assert dashboard.json()["task_counts"]["todo"] == 2
    assert dashboard.json()["task_counts"]["in_progress"] == 1


def test_workspace_key_protects_api(tmp_path, monkeypatch):
    use_temp_store(tmp_path, monkeypatch)
    monkeypatch.setenv("WORKSPACE_ACCESS_KEY", "test-owner-key")
    client = TestClient(web.app)
    assert client.get("/health").status_code == 200
    assert client.get("/api/dashboard").status_code == 401
    assert client.get("/api/dashboard", headers={"X-Workspace-Key": "wrong"}).status_code == 401
    assert client.get("/api/dashboard", headers={"X-Workspace-Key": "test-owner-key"}).status_code == 200
