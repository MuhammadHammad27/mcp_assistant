# MCP Agency Operations Assistant

A local-first Model Context Protocol (MCP) server for an agency owner who wants to turn a client brief into a project plan, saved tasks, and a client-ready proposal.

## What it does

1. The owner enters a client brief.
2. The MCP tool creates a structured project plan.
3. The owner creates or generates delivery tasks.
4. The assistant drafts a proposal from the saved project.
5. The owner downloads a polished PDF proposal for client review or sharing.
6. The dashboard shows projects, task counts, a Kanban board, and a live activity log.

## Real MCP tools

- `create_project_plan`
- `create_tasks`
- `list_tasks`
- `update_task_status`
- `draft_proposal`

The server also exposes the `agency://dashboard` resource with project/task counts and recent tool activity, plus a reusable `agency_brief_workflow` prompt.

## Stack

- **Python 3.13**
- **Official MCP Python SDK v2**
- **FastAPI** local dashboard
- **SQLite** locally / **PostgreSQL** in hosted deployment
- **Vanilla HTML, CSS and JavaScript** UI
- **ReportLab** client-ready proposal PDF export
- **Pytest** automated checks

## Local data and cost

All project data is stored in `data/agency.db`. This MVP has no paid hosting and no paid AI API. The server can be connected to an MCP host over standard MCP transport, while the dashboard provides a visible demo workflow.

## Run locally

```powershell
cd "D:\D\work\code\portfolio\mcp-agency-operations"
.\.venv\Scripts\python -m pytest tests -q
.\.venv\Scripts\python -m uvicorn agency_ops.web:app --app-dir src --host 127.0.0.1 --port 8765
```

Open the local dashboard at `http://127.0.0.1:8765`.

## Run with MCP Inspector

```powershell
cd "D:\D\work\code\portfolio\mcp-agency-operations"
.\.venv\Scripts\python -m mcp dev src\agency_ops\server.py
```

The Inspector opens a local tool UI where the real MCP tools can be tested directly.

## Verified workflow

The test suite covers the full local workflow:

- Create a client project from a brief
- Generate three starter tasks and add a custom task
- Update a saved task status
- Read the saved task list
- Draft and save a proposal
- Download the saved proposal as a validated PDF
- Confirm dashboard metrics and Kanban data update

## Scope of this MVP

This is a local operations assistant. It deliberately does not send emails, change third-party systems, or use paid AI services. Those actions can be added later with user approval and explicit tool permissions.

## Proposal PDF export

After drafting a proposal in the project workspace, select **Download proposal PDF**. The generated document contains the client name, project goal, scope, delivery timeline, investment note, and next step. It is created locally in memory and downloads directly through the dashboard; no external storage or paid document service is used.

## Live deployment

The dashboard is deployed on Render:

- **Live URL:** https://mcp-assistant-58tz.onrender.com
- **Runtime:** Docker on Render Free
- **Branch:** `main`
- **Region:** Virginia, US East

The first public deployment completed successfully on October 16, 2026. Render logs confirmed the FastAPI server started and the dashboard returned `200 OK` at `/`.

The Render Free instance sleeps after 15 minutes without traffic. Opening the URL starts it again, and the first request can take about a minute.
## Protected deployment

The public dashboard and remote Streamable HTTP MCP endpoint are designed to run with a single owner access key. Set `APP_ENV=production` and a strong `WORKSPACE_ACCESS_KEY` in the hosting platform's secret manager. The dashboard asks for this key once per browser session and sends it only as an HTTP request header. The remote MCP endpoint is mounted at `/mcp` and requires the same header.

Do not publish the local `data/agency.db` file. Use a managed persistent data store or a mounted encrypted volume before storing real client work in production.

## Hosted configuration

Set these values in Render's secret environment variables:

| Variable | Purpose |
| --- | --- |
| `APP_ENV` | Set to `production` to require dashboard authentication. |
| `WORKSPACE_ACCESS_KEY` | A long private owner key used for the dashboard and remote MCP endpoint. |
| `DATABASE_URL` | A Neon PostgreSQL connection string for durable project, task, proposal, and activity data. |

Never commit these values to GitHub. The service can run without `DATABASE_URL`, but then it uses local SQLite storage. On Render Free, local files are ephemeral and data can be lost after a restart or sleep cycle. Use Neon before storing real client work.

For deployment history and operational checks, see [DEPLOYMENT_NOTES.md](DEPLOYMENT_NOTES.md).
