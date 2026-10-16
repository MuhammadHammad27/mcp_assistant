# MCP Agency Operations Assistant — Deployment Notes

## Current live service

| Item | Value |
| --- | --- |
| Application | MCP Agency Operations Assistant |
| Hosting | Render Free web service |
| Public URL | https://mcp-assistant-58tz.onrender.com |
| Source branch | `main` |
| Region | Virginia, US East |
| Deployment date | October 16, 2026 |

## Verification completed

- Render reported **Deploy succeeded** and **Live**.
- The FastAPI/Uvicorn server completed startup successfully.
- The deployed dashboard returned `200 OK` for `GET /`.
- The public dashboard opened successfully in a browser.

## Environment variables

Configure these in Render's Environment page. Keep the values private.

| Variable | Required | Notes |
| --- | --- | --- |
| `APP_ENV` | Yes | Use `production`. |
| `WORKSPACE_ACCESS_KEY` | Yes | Use a long, unique owner key. |
| `DATABASE_URL` | Recommended | Neon PostgreSQL connection string. Required for durable hosted data. |

## Free-service behavior

- A free Render web service sleeps after 15 minutes with no traffic.
- The next visitor starts it again; the initial response can take around a minute.
- Free-service local files are temporary. Do not rely on local SQLite for real client projects.
- GitHub remains the source of truth for the application code.

## Next operational task

Create a free Neon PostgreSQL database and add its connection string as `DATABASE_URL` in Render. Then create a test project, task, and proposal in the live dashboard to confirm that data remains available after a service restart.
