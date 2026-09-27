---
name: agentic-dag
description: Track workspace tasks as a DAG with persistent state, Telegram review notifications, and a web observability UI scoped to the current workspace where a harness is run.
---

# Agentic DAG & Workspace Progress Tracker Skill

Use this skill when you need to maintain project progress, structure work into dependent tasks (DAG), store persistent state/memory across coding sessions, trigger human-in-the-loop reviews via Telegram, or expose visual observability via a web UI.

---

## 1. Setup & Environment

Before using the skill capabilities, ensure the project dependencies and environment variables are set up:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Environment Configuration (`.env`)

Create or check `.env` at repository root:

```dotenv
# Required for Telegram notifications & Telegram bot commands
TELEGRAM_BOT_TOKEN=your_bot_token_here

# Optional configuration defaults
DAG_STATE_FILE=dag_state.json
PROJECT_TITLE=Workspace Progress
WEB_PORT=8080
```

---

## 2. Workspace Progress & Memory Persistence

The task DAG is saved automatically to `DAG_STATE_FILE` (`dag_state.json` by default). Tasks are nodes, and dependencies are directed edges (`from_id -> to_id`).

### Node Status Conventions

Node labels start with status prefixes:

- `Backlog — <title>` (Gray)
- `To Do — <title>` (Amber)
- `In Progress — <title>` (Blue)
- `Review — <title>` (Purple)
- `Done — <title>` (Green)
- `Archived — <title>` (Dark Gray)

### Python API

```python
from src.dag import Dag

dag = Dag()

# Add a node
dag.add_node("task-1", "To Do — Implement authentication feature")

# Add a dependency (task-2 depends on task-1 finishing)
dag.add_edge("task-1", "task-2")

# Save and load occur automatically on mutations
```

### Fast CLI for Task Execution & Checkpointing (`src.dag_cli`)

Harnesses and autonomous agents can manage task lifecycle, checkpoints, and dependency queries directly via CLI:

```bash
# Get the next actionable / unblocked task
python -m src.dag_cli next

# Save a progress checkpoint (findings, artifacts, next immediate step)
python -m src.dag_cli checkpoint <node_id> \
  --status "In Progress" \
  --findings "Diagnosed schema issue" \
  --artifacts "schema.sql" \
  --next "Run database migrations"

# Complete a task and unlock downstream dependencies
python -m src.dag_cli complete <node_id> --findings "Migrations executed successfully"

# List active or all tasks with their blockers
python -m src.dag_cli list --all

# Add a task with dependencies
python -m src.dag_cli add <node_id> "<title>" --depends-on <dep1,dep2>
```

---

## 3. Human-in-the-Loop Telegram Notifications

### Running the Bot

Start the Telegram bot handler:

```bash
python -m src.main
```
Or start it programmatically / via the Web UI API at `POST /api/telegram/start`.

### Registering Chat ID

In Telegram, the human reviewer sends `/register` to the bot to record the chat ID locally.

### Triggering Human Review

When an agent reaches a checkpoint requiring human approval, use reply-push by
default. Start the local web server and its Telegram bot first, then run:

```bash
python -m src.run_web
# In another shell: POST /api/telegram/start
python -m src.notify <node_id> "<message detailing what needs review>"
```

If `PROJECT_TITLE` is set in `.env` or passed via `--project-title "<title>"`, the notification message includes `Project: <title>` at the top.

The CLI waits for the direct Telegram reply by default and prints its JSON
result to stdout. Use `--no-wait` only when the caller explicitly needs a
send-only notification.

### Waiting for the Human Reply (Push to Harness)

Instead of polling `dag_state.json`, harnesses can block until the human responds:

**CLI (recommended for agents):**

```bash
python -m src.notify <node_id> "<message>" --timeout 300
```
This sends the notification *and* blocks until the reply arrives, then prints the result as JSON to stdout:

```json
{"node_id": "task-1", "status": "In Progress", "response": "approved, looks good", "chat_id": 123456}
```

**HTTP — send + wait in one call:**

```bash
curl -X POST http://localhost:8080/api/telegram/notify \
  -H 'Content-Type: application/json' \
  -d '{"node_id": "task-1", "message": "Please review", "project_title": "Workspace Progress", "wait": true, "timeout": 300}'
```

**HTTP — standalone wait (if notification was sent separately):**

```bash
curl "http://localhost:8080/api/telegram/reviews/task-1/wait?timeout=300"
```

> **Note:** Reply-push is the default. It and the wait endpoints require the web server (`python -m src.run_web`) to be running with the bot started.

### Automatic Decision Routing

When human reviewers reply to the Telegram notification:

- Replies beginning with `approved`, `yes`, `proceed`, or `continue` automatically set the node status to `In Progress — <title> — Approved: <notes>`.
- Replies beginning with `rejected`, `no`, `changes requested`, or `revise` automatically set the node status to `To Do — <title> — Changes requested: <notes>`.

---

## 4. Web UI & Observability

Launch the Web UI control panel and visualizer:

```bash
python -m src.run_web
```

- **Control Panel**: `http://localhost:8080/` (D3 force-directed DAG, node/edge management, Telegram bot controls, settings).
- **Kanban Board**: `http://localhost:8080/visualize` (Swimlanes grouped by status label with curved dependency arrows).
- **Graph Canvas**: `http://localhost:8080/graph` (Zoomable D3 graph for large DAG navigation).

### Key HTTP Endpoints

- `GET /api/dag` - Retrieve nodes and dependency edges.
- `POST /api/dag/nodes` - Create a node: `{"id": "...", "label": "..."}`.
- `POST /api/dag/edges` - Create a dependency: `{"source": "...", "target": "..."}`.
- `POST /api/telegram/notify` - Trigger a human review notification and wait for the reply by default. Set `"wait": false` only for send-only delivery.
- `GET /api/telegram/reviews/{node_id}/wait?timeout=300` - Block until a review response arrives for the given node.

---

## 5. Agent Workflow Guidelines & Compaction Routine

When assigned a workspace task:

1. **Workspace Scope**: Ensure all DAG operations and task tracking are strictly confined to the current workspace where the harness is run.
2. **Load/Inspect DAG**: Run `python -m src.dag_cli next` or query `GET /api/dag` to immediately rehydrate active context and next actions.
3. **Track New Sub-tasks**: Add new task nodes and dependency edges as requirements are decomposed (`python -m src.dag_cli add ...`).
4. **Autonomous Checkpointing**: Record checkpoints after atomic progress (`python -m src.dag_cli checkpoint ...`) with findings, artifacts, and next immediate steps.
5. **Context Compaction Flush**: Before context runs out or between long turns, flush all critical findings into the active node checkpoint.
6. **Request Review**: Move node to `Review`, then invoke `python -m src.notify` when human feedback or sign-off is needed.
7. **Complete & Unlock**: Verify tests and mark node `Done` via `python -m src.dag_cli complete <node_id>`.
