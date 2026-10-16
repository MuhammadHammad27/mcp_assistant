"""Protected dashboard and remote MCP endpoint for Agency Operations."""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agency_ops import server
from agency_ops.pdf_export import build_proposal_pdf

store = server.store
app = FastAPI(title="MCP Agency Operations Dashboard", version="0.2.0")
DASHBOARD_DIR = Path(__file__).parent / "dashboard"
app.mount("/assets", StaticFiles(directory=DASHBOARD_DIR), name="assets")


def workspace_access_key() -> str:
    return os.getenv("WORKSPACE_ACCESS_KEY", "").strip()


def request_has_access(request: Request) -> bool:
    expected = workspace_access_key()
    if not expected:
        return True
    supplied = request.headers.get("x-workspace-key", "")
    return bool(supplied) and secrets.compare_digest(supplied, expected)


@app.on_event("startup")
async def validate_production_configuration() -> None:
    if os.getenv("APP_ENV", "local").lower() == "production" and not workspace_access_key():
        raise RuntimeError("WORKSPACE_ACCESS_KEY must be set before running the public deployment.")


@app.middleware("http")
async def protect_workspace(request: Request, call_next):
    protected_path = request.url.path.startswith("/api/") or request.url.path.startswith("/mcp")
    if protected_path and not request_has_access(request):
        return JSONResponse(status_code=401, content={"detail": "Workspace access key required."})
    return await call_next(request)


class ProjectRequest(BaseModel):
    client_name: str = Field(min_length=1, max_length=120)
    project_name: str = Field(min_length=1, max_length=160)
    brief: str = Field(min_length=10, max_length=4000)
    timeline_days: int = Field(default=7, ge=1, le=365)


class TasksRequest(BaseModel):
    tasks: list[dict[str, Any]] = Field(min_length=1, max_length=30)


class TaskStatusRequest(BaseModel):
    status: str = Field(pattern="^(todo|in_progress|blocked|done)$")


class ProposalRequest(BaseModel):
    scope: str = Field(min_length=5, max_length=4000)
    timeline: str = Field(min_length=2, max_length=500)
    investment_note: str = Field(default="To be agreed", max_length=500)


def client_error(error: ValueError) -> HTTPException:
    return HTTPException(status_code=422, detail=str(error))


@app.get("/health")
def health():
    return {
        "status": "ok",
        "mode": "protected" if workspace_access_key() else "local",
        "mcp_server": "Agency Operations Assistant",
    }


@app.get("/api/dashboard")
def dashboard():
    return server.read_dashboard()


@app.get("/api/projects")
def list_projects():
    return {"projects": store.list_projects()}


@app.get("/api/tasks")
def list_all_tasks(status: str = "all"):
    try:
        return server.list_tasks(status=status)
    except ValueError as error:
        raise client_error(error) from error


@app.get("/api/projects/{project_id}/tasks")
def list_tasks(project_id: int):
    try:
        return server.list_tasks(project_id=project_id)
    except ValueError as error:
        raise client_error(error) from error


@app.patch("/api/tasks/{task_id}")
def update_task_status(task_id: int, request: TaskStatusRequest):
    try:
        return server.update_task_status(task_id, request.status)
    except ValueError as error:
        raise client_error(error) from error


@app.post("/api/projects", status_code=201)
def create_project(request: ProjectRequest):
    try:
        return server.create_project_plan(
            client_name=request.client_name,
            project_name=request.project_name,
            brief=request.brief,
            timeline_days=request.timeline_days,
        )
    except ValueError as error:
        raise client_error(error) from error


@app.post("/api/projects/{project_id}/tasks", status_code=201)
def create_tasks(project_id: int, request: TasksRequest):
    try:
        return server.create_tasks(project_id, request.tasks)
    except ValueError as error:
        raise client_error(error) from error


@app.post("/api/projects/{project_id}/starter-tasks", status_code=201)
def create_starter_tasks(project_id: int):
    try:
        project = store.get_project(project_id)
        starter_title = "Confirm scope and success criteria"
        if any(task["title"] == starter_title for task in store.list_tasks(project_id)):
            raise ValueError("Starter tasks already exist for this project. Add a custom task instead.")
        timeline = project["plan"]["timeline_days"]
        tasks = [
            {"title": starter_title, "description": "Turn the approved brief into a clear delivery checklist.", "priority": "high", "status": "todo"},
            {"title": "Produce the first delivery draft", "description": f"Build the main deliverable within the {timeline}-day timeline.", "priority": "high", "status": "todo"},
            {"title": "Run review and prepare client handoff", "description": "Collect feedback, resolve final issues, and prepare handoff notes.", "priority": "medium", "status": "todo"},
        ]
        return server.create_tasks(project_id, tasks)
    except ValueError as error:
        raise client_error(error) from error


@app.post("/api/projects/{project_id}/proposal", status_code=201)
def create_proposal(project_id: int, request: ProposalRequest):
    try:
        return server.draft_proposal(project_id, request.scope, request.timeline, request.investment_note)
    except ValueError as error:
        raise client_error(error) from error


@app.get("/api/proposals/{proposal_id}/export.pdf")
def export_proposal_pdf(proposal_id: int):
    try:
        proposal = store.get_proposal(proposal_id)
        project = store.get_project(proposal["project_id"])
        filename = "".join(char if char.isalnum() else "-" for char in project["name"]).strip("-")
        return StreamingResponse(
            build_proposal_pdf(project, proposal),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename or "proposal"}-proposal.pdf"'},
        )
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


# Mount a standards-based Streamable HTTP MCP server at /mcp. It shares the same access-key middleware.
app.mount("/mcp", server.mcp.streamable_http_app(streamable_http_path="/", host="0.0.0.0"))


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(DASHBOARD_DIR / "index.html")
