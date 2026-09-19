# Agentic DAG & Telegram Bot Project

This repository provides a lightweight framework for agentic workflows that can:

- Define a directed acyclic graph (DAG) of tasks or knowledge nodes.
- Interact through a Telegram bot to add, inspect, and manage the DAG.
- Render the DAG as a label-lane Kanban board with dependency arrows.
- Register Telegram chats for proactive human-review notifications.

## Registering as an Agent Skill

To add this repository to an AI coding agent as a skill, simply copy and paste the following prompt into your agent:

```text
Install the repository https://github.com/lumintulogic/agentic-dag as one skill directory scoped strictly to the current workspace where a harness is run. The harness should acquire its own native repository-scoped skill discovery location using the most efficient method. Keep the skill source linked to its upstream repository as a Git submodule at that location, rather than copying or vendoring it, and preserve the workspace's `.gitmodules` entry. Update it with `git submodule update --remote --merge <skill-path>` and commit the resulting submodule pointer. Treat the installed directory's root `SKILL.md` as the only canonical manifest. Use the skill to track workspace progress using a DAG task graph, maintain persistent memory across sessions, send Telegram notifications for human-in-the-loop review, and provide a web UI for human observability. Before taking task actions, read the root `SKILL.md` completely, especially **Waiting for the Human Reply (Push to Harness)**. Use its reply-push workflow by default whenever sending a review notification.
```

## Project Layout

```text
agentic-dag/
├── src/
│   ├── dag.py            # DAG persistence and the optional state-file override.
│   ├── bot.py            # Telegram command handlers.
│   ├── notifications.py  # Local registered-chat storage.
│   ├── notify.py         # CLI sender for human-review notifications.
│   ├── visualize.py      # Mermaid generation utilities.
│   ├── main.py           # Telegram bot entry point.
│   ├── run_web.py        # Web server entry point.
│   ├── web.py            # FastAPI API and bot manager.
│   └── static/
│       ├── index.html    # Control-panel single-page app.
│       └── visualize.html # Kanban dependency visualization page.
├── requirements.txt
├── dag_state.json        # Default persisted DAG (created on first save).
└── README.md
```

## Quick Start

1. Install dependencies:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Create a Telegram bot through `@BotFather`, then configure `TELEGRAM_BOT_TOKEN` as described below.

3. Start the bot:

   ```bash
   python -m src.main
   ```

4. In the Telegram chat that should receive human-review requests, send:

   ```text
   /register
   ```

   The bot stores that chat ID locally. Do not share the chat ID or bot token in source control.

## Environment Variables

Create a `.env` file at the repository root. Only the token is required:

```dotenv
# Required
TELEGRAM_BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN_HERE

# Optional: defaults to ./dag_state.json beside this repository.
DAG_STATE_FILE=/path/to/dag_state.json

# Optional: defaults to ./telegram_notification_chat_ids.json at the repository root.
TELEGRAM_NOTIFICATION_REGISTRY=/path/to/telegram_notification_chat_ids.json

# Optional: defaults beside DAG_STATE_FILE as dag_export.json.
DAG_EXPORT_FILE=/path/to/dag_export.json

# Optional: shown in web page headings and browser-tab titles. Restart the web
# server after changing this value.
PROJECT_TITLE=My Project
```

`DAG_STATE_FILE` is useful when the tracker code and its persisted project state live in separate directories. The bot loads this file on startup and saves every DAG mutation back to the same path. `PROJECT_TITLE` defaults to `DAG Project` when it is unset or blank.

## Web UI

The FastAPI control panel provides a browser interface for the DAG, Telegram bot controls, and persisted state-file selection.

Start it from the repository root:

```bash
python -m src.run_web
```

The server binds only to `127.0.0.1`, prefers port `8080`, and automatically tries the next available port if it is occupied; it prints the selected address at startup. Set `WEB_PORT` to choose the first port to try. Open the printed `http://localhost:<port>` address. When using a forwarded development-server URL, open its forwarded `/proxy/<port>/` path instead. The UI uses paths relative to that application base, so its API calls work both at the domain root and behind a path-based proxy.

### What it provides

- Interactive D3 force-directed DAG with directed edges, drag, zoom/pan, selection, and a node context menu.
- Node and edge CRUD controls, with cycle protection enforced by the API.
- Telegram bot start/stop controls, registered-chat management, pending-review status, and notification sending.
- State-file selection with recent-file history in browser `localStorage`.
- A horizontally scrollable Kanban page at `/visualize`; node labels form lanes and curved arrows connect dependencies.
- A dedicated zoomable D3 Graph Canvas at `/graph` for navigating large DAGs without shrinking them to fit; clicking a node opens a persistent detail panel.

The control panel polls the DAG and Telegram status every five seconds. It retains the existing node layout during ordinary polling; the force simulation is reheated only when nodes, labels, or edges change.

### Architecture

```text
Browser control panel / Kanban page
                 │ HTTP
                 ▼
FastAPI server (src/web.py)
 ├── DAG and state-file API
 ├── Telegram bot manager (background thread)
 └── static frontend
                 │
                 ▼
NetworkX DAG persisted as JSON (DAG_STATE_FILE)
```

The web API reloads its configured DAG state before reads and mutations. Set `DAG_STATE_FILE` before starting the server to ensure that the web UI and Telegram bot use the same persisted DAG. The embedded Telegram bot runs in a daemon thread with its own asyncio event loop.

### Control-panel behavior

The page has a D3 graph at left and tabs for Nodes, Edges, Telegram, and Settings. Node label prefixes determine the graph color:

| Status | Color |
|---|---|
| In Progress | Blue |
| To Do / Next | Amber |
| Review / To Review | Purple |
| Done | Green |
| Backlog | Gray |
| Archived | Dark gray |

The Settings tab applies a state-file path to the running server and saves it locally for the current browser. It maintains these `localStorage` keys:

| Key | Description |
|---|---|
| `dag_state_file_path` | Last state-file path applied by this browser. |
| `dag_recent_files` | Up to ten recently used state-file paths. |

### HTTP API

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/config/state-file` | Get the active state-file path. |
| `PUT` | `/api/config/state-file` | Set the active state-file path: `{"path": "..."}`. |
| `GET` | `/api/dag` | Get the project title, nodes (including normalized `dependencies`), and edges. |
| `GET` | `/api/dag/mermaid` | Get generated Mermaid flowchart source. |
| `POST` | `/api/dag/nodes` | Add a node: `{"id": "...", "label": "..."}`. |
| `PUT` | `/api/dag/nodes/{node_id}` | Update a node label. |
| `DELETE` | `/api/dag/nodes/{node_id}` | Delete a node and its connected edges. |
| `POST` | `/api/dag/edges` | Add an edge: `{"source": "...", "target": "..."}`. |
| `DELETE` | `/api/dag/edges` | Delete an edge using `source` and `target` query parameters. |
| `GET` | `/api/telegram/status` | Get bot, registered-chat, and pending-review status. |
| `POST` | `/api/telegram/start` | Start the Telegram bot in the server process. |
| `POST` | `/api/telegram/stop` | Stop the Telegram bot. |
| `GET` | `/api/telegram/chats` | List registered chat IDs. |
| `DELETE` | `/api/telegram/chats/{chat_id}` | Remove a registered chat. |
| `POST` | `/api/telegram/notify` | Send a task-linked notification. Optionally set `"wait": true` and `"timeout": 300` to block for reply. |
| `GET` | `/api/telegram/reviews/{node_id}/wait` | Block until a review response arrives for `{node_id}` (`?timeout=300`). |
| `GET` | `/visualize` | Render the current DAG as a label-lane Kanban board. |
| `GET` | `/graph` | Open the full-screen D3 Graph Canvas. |

### Deployment notes

- The server serves the static control panel at `/` and enables permissive CORS for development.
- The control panel and Graph Canvas load D3.js from a CDN; the Kanban view has no external frontend dependency.
- The UI does not provide authentication. Put it behind suitable access controls before exposing it publicly.

### Web UI roadmap

- Node metadata editing beyond labels.
- Bulk import/export from the UI.
- Authentication and authorization for production deployments.
- WebSocket updates in place of polling.
- Persisted graph-layout coordinates.
- Light-theme and mobile-layout support.

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcomes the user and lists commands. |
| `/register` | Registers the current Telegram chat for human-review notifications. Repeating it is safe. |
| `/add_node <node_id> <label>` | Adds a node to the DAG. |
| `/add_edge <from_id> <to_id>` | Adds a directed edge, provided the graph stays acyclic. |
| `/show` | Prints a concise text representation of the DAG. |
| `/visualize` | Replies with Mermaid JS syntax. |
| `/export` | Sends the DAG JSON export; the destination is controlled by `DAG_EXPORT_FILE`. |

## Human-Review Notifications

After at least one chat has sent `/register`, start `python -m src.run_web` and its Telegram bot. Then send a notification from the repository root:

```bash
python -m src.notify <node_id> "Action needed: review the current DAG task."
```

Reply-push is the default: the command blocks until the reviewer replies and
prints the response as JSON. Use `--no-wait` only for a deliberately send-only
notification.

If `PROJECT_TITLE` is set in the environment or passed via `--project-title <title>`, the Telegram notification message explicitly includes `Project: <title>` at the top.

### Waiting for Human Reply (Push to Harness)

Harnesses can block until the human responds rather than polling `dag_state.json`:

**CLI (default):**
```bash
python -m src.notify <node_id> "Review needed" --timeout 300 --project-title "My Project"
```
This sends the notification and blocks until a reply arrives, printing the review result JSON to `stdout`.

**HTTP API:**
- `POST /api/telegram/notify` with `{"node_id": "...", "message": "...", "project_title": "My Project", "timeout": 300}`; set `"wait": false` only for send-only delivery.
- `GET /api/telegram/reviews/{node_id}/wait?timeout=300`

The notification command sends a task-linked message to every locally registered chat and records each sent message ID locally. Reply directly to that notification: replies beginning with `approved`, `yes`, `proceed`, or `continue` move the node to `In Progress`; replies beginning with `rejected`, `no`, `changes requested`, or `revise` move it to `To Do`; every other reply is recorded while the node stays in `Review`. The command fails safely if no chat has registered. The chat registry is local state and should be excluded from version control.

The sender emits flushed UTC diagnostics for `send_started`, Telegram acceptance, reply-mapping registration, and completion. They include the DAG node and Telegram message ID, but never a chat ID, bot token, or notification body. A failed send or mapping registration exits non-zero immediately after attempting the remaining registered recipients.

## Kanban Visualization

When the web server is running, open `/visualize` for the Kanban rendering of the current DAG. Each card's label determines its lane. Existing workflow labels such as `To Do — Task title` use the leading status as the lane and the remainder as the card title. Directed DAG edges are exposed as each target card's `dependencies` array, and persisted dependency metadata is merged with them. The board draws dependencies as compact curved arrows from the dependency to the dependent card. When exactly one endpoint is visible, its off-screen counterpart is parked as a clickable proxy in the reserved area at the top or bottom of its lane and the arrow continues to that proxy. Connections whose two endpoints are off-screen produce neither a proxy nor a curve. Card summaries are truncated to fit their borders, and selecting a card or parked proxy opens its complete details in a modal.

The Telegram `/visualize` command and `/api/dag/mermaid` endpoint continue to provide Mermaid source for text-based clients; the browser visualization itself no longer loads or renders Mermaid.

## Persistence

The DAG is persisted as NetworkX node-link JSON. By default it is stored in `dag_state.json` at the repository root. Set `DAG_STATE_FILE` to place it elsewhere; node metadata can hold compact task labels as well as richer project context.

## License

MIT
