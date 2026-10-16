"""MCP server exposing agency planning operations as real tools."""

from __future__ import annotations

from typing import Any

from mcp.server import MCPServer

from agency_ops.database import AgencyStore

mcp = MCPServer("Agency Operations Assistant")
store = AgencyStore()
store.initialize()


def build_plan(brief: str, timeline_days: int) -> dict[str, Any]:
    return {
        "objective": brief.strip(),
        "timeline_days": timeline_days,
        "phases": [
            {"name": "Discovery", "outcome": "Clarify goals, audience, scope and constraints."},
            {"name": "Production", "outcome": "Build the agreed deliverables and track work."},
            {"name": "Review", "outcome": "Review output, collect feedback and prepare handoff."},
        ],
        "success_criteria": ["Clear approved scope", "Visible task ownership", "Client-ready proposal"],
    }


@mcp.tool()
def create_project_plan(client_name: str, project_name: str, brief: str, timeline_days: int = 7) -> dict[str, Any]:
    """Create a client project and a structured delivery plan from the supplied brief."""
    if timeline_days < 1 or timeline_days > 365:
        raise ValueError("timeline_days must be between 1 and 365")
    plan = build_plan(brief, timeline_days)
    project = store.create_project(client_name, project_name, brief, plan)
    return {"project": project, "message": "Project plan created. Create tasks next."}


@mcp.tool()
def create_tasks(project_id: int, tasks: list[dict[str, Any]]) -> dict[str, Any]:
    """Save one or more structured tasks for a project. Each task needs title; optional fields are description, priority, status and due_date."""
    created = store.create_tasks(project_id, tasks)
    return {"project_id": project_id, "created_tasks": created, "count": len(created)}


@mcp.tool()
def list_tasks(project_id: int | None = None, status: str = "all") -> dict[str, Any]:
    """List project tasks. Optionally filter by project ID and by todo, in_progress, blocked, done, or all."""
    tasks = store.list_tasks(project_id, status)
    return {"tasks": tasks, "count": len(tasks)}


@mcp.tool()
def update_task_status(task_id: int, status: str) -> dict[str, Any]:
    """Update an existing task to todo, in_progress, blocked, or done."""
    task = store.update_task_status(task_id, status)
    return {"task": task, "message": "Task status updated."}

@mcp.tool()
def draft_proposal(project_id: int, scope: str, timeline: str, investment_note: str = "To be agreed") -> dict[str, Any]:
    """Create and save a concise client proposal for an existing project."""
    project = store.get_project(project_id)
    content = f"""# Proposal: {project['name']}

**Client:** {project['client_name']}

## Project goal
{project['brief']}

## Scope
{scope.strip()}

## Delivery timeline
{timeline.strip()}

## Investment
{investment_note.strip()}

## Next step
Approve the scope so production tasks can begin.
"""
    proposal = store.save_proposal(project_id, content)
    return {"proposal": proposal, "message": "Proposal drafted and saved."}


@mcp.resource("agency://dashboard")
def read_dashboard() -> dict[str, Any]:
    """Read current project counts, task status counts and recent tool activity."""
    return store.dashboard()


@mcp.prompt()
def agency_brief_workflow(brief: str) -> str:
    """Create a reusable prompt that guides an MCP host through an agency brief."""
    return f"""You are an agency operations assistant. Work from this client brief:

{brief}

First create a project plan. Then create focused tasks. Finally draft a client-ready proposal. Explain each tool result clearly and do not claim external actions were performed."""


if __name__ == "__main__":
    mcp.run()