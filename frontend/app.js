// Plain JS frontend -- no build step, no framework. Talks to the FastAPI
// backend over fetch(). Every response's X-Request-ID header is surfaced in
// the UI so you can copy it and grep for it directly in Loki while testing
// the metrics -> logs -> traces correlation workflow.

const API_BASE = window.API_BASE || "/backend";

const taskForm = document.getElementById("task-form");
const titleInput = document.getElementById("title");
const descInput = document.getElementById("description");
const taskList = document.getElementById("task-list");
const emptyState = document.getElementById("empty-state");
const refreshBtn = document.getElementById("refresh-btn");
const lastRequestId = document.getElementById("last-request-id");
const debugStatus = document.getElementById("debug-status");

async function apiFetch(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const reqId = res.headers.get("X-Request-ID");
  if (reqId) {
    lastRequestId.textContent = `Last request id: ${reqId}`;
  }
  if (!res.ok && res.status !== 204) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${res.status})`);
  }
  return res.status === 204 ? null : res.json();
}

function renderTasks(tasks) {
  taskList.innerHTML = "";
  emptyState.hidden = tasks.length > 0;

  for (const task of tasks) {
    const li = document.createElement("li");
    li.className = "task-item" + (task.completed ? " completed" : "");

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = task.completed;
    checkbox.addEventListener("change", () => toggleTask(task.id, checkbox.checked));

    const span = document.createElement("span");
    span.className = "title";
    span.textContent = task.description ? `${task.title} — ${task.description}` : task.title;

    const del = document.createElement("button");
    del.className = "delete";
    del.textContent = "Delete";
    del.addEventListener("click", () => deleteTask(task.id));

    li.append(checkbox, span, del);
    taskList.appendChild(li);
  }
}

async function loadTasks() {
  try {
    const tasks = await apiFetch("/tasks");
    renderTasks(tasks);
  } catch (err) {
    console.error("Failed to load tasks", err);
  }
}

async function createTask(title, description) {
  await apiFetch("/tasks", {
    method: "POST",
    body: JSON.stringify({ title, description: description || null }),
  });
  await loadTasks();
}

async function toggleTask(id, completed) {
  await apiFetch(`/tasks/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ completed }),
  });
  await loadTasks();
}

async function deleteTask(id) {
  await apiFetch(`/tasks/${id}`, { method: "DELETE" });
  await loadTasks();
}

taskForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const title = titleInput.value.trim();
  if (!title) return;
  await createTask(title, descInput.value.trim());
  titleInput.value = "";
  descInput.value = "";
});

refreshBtn.addEventListener("click", loadTasks);

document.querySelectorAll("[data-debug]").forEach((btn) => {
  btn.addEventListener("click", async () => {
    const kind = btn.dataset.debug;
    debugStatus.textContent = `Triggering /debug/${kind} ...`;
    try {
      await apiFetch(`/debug/${kind}`);
      debugStatus.textContent = `/debug/${kind} completed successfully.`;
    } catch (err) {
      debugStatus.textContent = `/debug/${kind} failed as expected: ${err.message}`;
    }
  });
});

loadTasks();