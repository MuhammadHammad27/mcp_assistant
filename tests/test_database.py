from agency_ops.database import AgencyStore


def test_project_task_proposal_and_dashboard(tmp_path):
    store = AgencyStore(tmp_path / "agency.db")
    store.initialize()
    project = store.create_project("Acme", "Launch site", "Build a landing page", {"objective": "Launch"})
    tasks = store.create_tasks(project["id"], [{"title": "Write project brief", "priority": "high"}])
    proposal = store.save_proposal(project["id"], "Proposal content")

    assert tasks[0]["status"] == "todo"
    assert proposal["project_id"] == project["id"]
    assert store.list_tasks(project["id"])[0]["title"] == "Write project brief"
    assert store.dashboard()["project_count"] == 1


def test_invalid_task_priority_is_rejected(tmp_path):
    store = AgencyStore(tmp_path / "agency.db")
    store.initialize()
    project = store.create_project("Acme", "Launch site", "Build a landing page", {"objective": "Launch"})

    try:
        store.create_tasks(project["id"], [{"title": "Bad priority", "priority": "now"}])
    except ValueError as error:
        assert "priority" in str(error)
    else:
        raise AssertionError("Invalid priority should fail")