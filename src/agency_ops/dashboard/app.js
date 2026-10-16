const metrics = document.querySelector("#metrics");
const projects = document.querySelector("#projects");
const activity = document.querySelector("#activity");
const form = document.querySelector("#brief-form");
const message = document.querySelector("#form-message");
const workspaceTitle = document.querySelector("#workspace-title");
const workspaceCopy = document.querySelector("#workspace-copy");
const workspaceActions = document.querySelector("#workspace-actions");
const starterTasksButton = document.querySelector("#starter-tasks");
const draftProposalButton = document.querySelector("#draft-proposal");
const taskForm = document.querySelector("#task-form");
const taskMessage = document.querySelector("#task-message");
const tasks = document.querySelector("#tasks");
const proposal = document.querySelector("#proposal");
const proposalDownload = document.querySelector("#proposal-download");
const kanban = document.querySelector("#kanban");

let selectedProject = null;
let proposalToDownload = null;

function accessKey() {
  return sessionStorage.getItem("agencyWorkspaceKey") || "";
}

function apiHeaders(extra = {}) {
  const headers = {"Content-Type": "application/json", ...extra};
  if (accessKey()) headers["X-Workspace-Key"] = accessKey();
  return headers;
}

async function request(path, options = {}) {
  const response = await fetch(path, {...options, headers: apiHeaders(options.headers)});
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : null;
  if (!response.ok) throw new Error((payload && payload.detail) || "Request failed");
  return payload;
}

function escapeHtml(value) {
  const node = document.createElement("div");
  node.textContent = value || "";
  return node.innerHTML;
}

function statusOptions(current) {
  return ["todo", "in_progress", "blocked", "done"].map(status =>
    '<option value="' + status + '"' + (status === current ? " selected" : "") + ">" + status.replace("_", " ") + "</option>"
  ).join("");
}

function renderTasks(items) {
  tasks.innerHTML = items.length ? items.map(task =>
    '<article class="task"><div><strong>' + escapeHtml(task.title) + '</strong><span class="priority ' + escapeHtml(task.priority) + '">' + escapeHtml(task.priority) + '</span></div><p>' + escapeHtml(task.description || "No description provided.") + '</p><label class="task-status-label">Status<select class="task-status" data-task-id="' + task.id + '">' + statusOptions(task.status) + '</select></label></article>'
  ).join("") : '<p class="empty">No tasks for this project yet.</p>';
  tasks.querySelectorAll(".task-status").forEach(select => select.addEventListener("change", async () => {
    select.disabled = true;
    try {
      await request("/api/tasks/" + select.dataset.taskId, {method: "PATCH", body: JSON.stringify({status: select.value})});
      if (selectedProject) await openWorkspace(selectedProject, false);
      await refresh();
    } catch (error) { taskMessage.textContent = error.message; }
    finally { select.disabled = false; }
  }));
}

function renderKanban(items) {
  const columns = [["todo", "To do"], ["in_progress", "In progress"], ["blocked", "Blocked"], ["done", "Done"]];
  kanban.innerHTML = columns.map(([status, label]) => {
    const columnTasks = items.filter(task => task.status === status);
    const cards = columnTasks.length ? columnTasks.map(task => '<article class="kanban-card"><span class="priority ' + escapeHtml(task.priority) + '">' + escapeHtml(task.priority) + '</span><strong>' + escapeHtml(task.title) + '</strong><small>Project ' + task.project_id + '</small></article>').join("") : '<p class="kanban-empty">No tasks</p>';
    return '<section class="kanban-column ' + status + '"><header><span>' + label + '</span><b>' + columnTasks.length + '</b></header><div class="kanban-stack">' + cards + '</div></section>';
  }).join("");
}

async function openWorkspace(project, scroll = true) {
  selectedProject = project;
  workspaceTitle.textContent = project.name;
  workspaceCopy.textContent = project.client_name + " · " + project.plan.timeline_days + "-day plan";
  workspaceActions.hidden = false;
  taskForm.hidden = false;
  proposal.hidden = true;
  proposal.textContent = "";
  proposalDownload.hidden = true;
  proposalToDownload = null;
  const response = await request("/api/projects/" + project.id + "/tasks");
  const hasStarterTasks = response.tasks.some(task => task.title === "Confirm scope and success criteria");
  starterTasksButton.disabled = hasStarterTasks;
  starterTasksButton.textContent = hasStarterTasks ? "Starter tasks added" : "Create starter tasks";
  renderTasks(response.tasks);
  if (scroll) document.querySelector(".workspace-panel").scrollIntoView({behavior: "smooth", block: "start"});
}

async function refresh() {
  const results = await Promise.all([request("/api/dashboard"), request("/api/projects"), request("/api/tasks")]);
  const [dashboard, projectResponse, taskResponse] = results;
  const counts = dashboard.task_counts;
  metrics.innerHTML = [["Projects", dashboard.project_count], ["To do", counts.todo], ["In progress", counts.in_progress], ["Completed", counts.done]].map(item => '<div class="metric"><span>' + item[0] + '</span><strong>' + item[1] + '</strong></div>').join("");
  projects.innerHTML = projectResponse.projects.length ? projectResponse.projects.map(project => '<article class="project-card"><span>PROJECT ' + String(project.id).padStart(2, "0") + '</span><h3>' + escapeHtml(project.name) + '</h3><p>' + escapeHtml(project.client_name) + '</p><small>' + escapeHtml(project.brief) + '</small><button class="open-project" data-project-id="' + project.id + '">Open workspace</button></article>').join("") : '<p class="empty">No projects yet. Start with a client brief.</p>';
  projects.querySelectorAll(".open-project").forEach(button => button.addEventListener("click", () => {
    const project = projectResponse.projects.find(item => item.id === Number(button.dataset.projectId));
    if (project) openWorkspace(project).catch(error => { message.textContent = error.message; });
  }));
  renderKanban(taskResponse.tasks);
  activity.innerHTML = dashboard.recent_activity.length ? dashboard.recent_activity.map(item => '<div class="activity"><strong>' + escapeHtml(item.action) + '</strong><span>' + escapeHtml(item.entity_type) + '</span><small>' + new Date(item.created_at).toLocaleString() + '</small></div>').join("") : '<p class="empty">Tool activity will appear here.</p>';
}

async function unlockWorkspace() {
  const entered = window.prompt("Enter the workspace access key.");
  if (!entered) return;
  sessionStorage.setItem("agencyWorkspaceKey", entered.trim());
  try { await refresh(); message.textContent = "Protected workspace unlocked for this browser session."; }
  catch (error) { sessionStorage.removeItem("agencyWorkspaceKey"); message.textContent = error.message; }
}

function handleStartupError(error) {
  if (error.message === "Workspace access key required.") { unlockWorkspace(); return; }
  message.textContent = error.message;
}

form.addEventListener("submit", async event => {
  event.preventDefault();
  message.textContent = "Creating project plan...";
  const data = Object.fromEntries(new FormData(form)); data.timeline_days = Number(data.timeline_days);
  try { const result = await request("/api/projects", {method: "POST", body: JSON.stringify(data)}); message.textContent = "Plan created for " + result.project.client_name + ". Open it to create tasks and a proposal."; form.reset(); form.timeline_days.value = 7; await refresh(); await openWorkspace(result.project); }
  catch (error) { message.textContent = error.message; }
});

taskForm.addEventListener("submit", async event => {
  event.preventDefault(); if (!selectedProject) return; taskMessage.textContent = "Adding task...";
  const data = Object.fromEntries(new FormData(taskForm));
  try { await request("/api/projects/" + selectedProject.id + "/tasks", {method: "POST", body: JSON.stringify({tasks: [data]})}); taskForm.reset(); taskForm.priority.value = "medium"; taskMessage.textContent = "Custom task saved."; await openWorkspace(selectedProject, false); await refresh(); }
  catch (error) { taskMessage.textContent = error.message; }
});

starterTasksButton.addEventListener("click", async () => {
  if (!selectedProject) return; starterTasksButton.disabled = true; starterTasksButton.textContent = "Creating tasks...";
  try { await request("/api/projects/" + selectedProject.id + "/starter-tasks", {method: "POST"}); await openWorkspace(selectedProject, false); await refresh(); }
  catch (error) { taskMessage.textContent = error.message; }
});

draftProposalButton.addEventListener("click", async () => {
  if (!selectedProject) return; draftProposalButton.disabled = true; draftProposalButton.textContent = "Drafting...";
  try {
    const result = await request("/api/projects/" + selectedProject.id + "/proposal", {method: "POST", body: JSON.stringify({scope: "Project planning, delivery production, review, feedback handling and final handoff.", timeline: selectedProject.plan.timeline_days + " days", investment_note: "To be agreed after scope approval"})});
    proposal.textContent = result.proposal.content; proposal.hidden = false; proposalToDownload = result.proposal.id; proposalDownload.hidden = false; await refresh();
  } catch (error) { taskMessage.textContent = error.message; }
  finally { draftProposalButton.disabled = false; draftProposalButton.textContent = "Draft client proposal"; }
});

proposalDownload.addEventListener("click", async event => {
  event.preventDefault(); if (!proposalToDownload) return;
  try {
    const response = await fetch("/api/proposals/" + proposalToDownload + "/export.pdf", {headers: apiHeaders()});
    if (!response.ok) { const body = await response.json(); throw new Error(body.detail || "PDF download failed"); }
    const url = URL.createObjectURL(await response.blob()); const link = document.createElement("a"); link.href = url; link.download = "agency-proposal.pdf"; link.click(); URL.revokeObjectURL(url);
  } catch (error) { taskMessage.textContent = error.message; }
});

refresh().catch(handleStartupError);
