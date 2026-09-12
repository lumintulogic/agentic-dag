# PRD: DAG Control Panel — Web UI

> **Status**: Implemented (v1)
> **Last updated**: 2026-09-12

## 1. Overview

A web-based control panel for managing a Directed Acyclic Graph (DAG) of task/knowledge nodes, with integrated Telegram bot control for human-review notifications. The system extends an existing CLI/bot-based DAG tool with a browser-accessible interface.

## 2. Problem Statement

The existing DAG management system operates entirely through a Telegram bot and CLI commands. This limits usability:
- No visual representation of the DAG structure
- No easy way to see all nodes/edges at a glance
- Starting/stopping the Telegram bot requires terminal access
- Switching between different DAG state files requires environment variable changes and restarts

## 3. Goals

| # | Goal | Status |
|---|------|--------|
| G1 | Interactive DAG visualization with force-directed graph | ✅ Done |
| G2 | CRUD operations on nodes and edges via web UI | ✅ Done |
| G3 | Start/stop Telegram bot from the browser | ✅ Done |
| G4 | Manage registered Telegram chat IDs | ✅ Done |
| G5 | Send Telegram notifications from the UI | ✅ Done |
| G6 | Configure DAG state file path (persisted in localStorage) | ✅ Done |
| G7 | Auto-refresh to stay in sync with bot-side changes | ✅ Done |

## 4. Architecture

```
┌───────────────────────────────────────────────────────┐
│  Browser (Single-Page App)                            │
│  ┌─────────────────┐  ┌───────────────────────────┐   │
│  │ D3.js Force DAG  │  │  Control Panel (Tabs)     │   │
│  │ (left 60%)       │  │  • Nodes  • Edges         │   │
│  │                  │  │  • Telegram  • Settings    │   │
│  └─────────────────┘  └───────────────────────────┘   │
│  localStorage: state file path, recent files          │
└───────────────┬───────────────────────────────────────┘
                │  REST API (fetch)
┌───────────────┴───────────────────────────────────────┐
│  FastAPI Backend (src/web.py)                         │
│  ┌──────────┐ ┌────────────┐ ┌───────────────────┐    │
│  │ DAG CRUD │ │ TG Bot Mgr │ │ Config Endpoints  │    │
│  │ endpoints│ │ (threaded) │ │ (state file path) │    │
│  └────┬─────┘ └─────┬──────┘ └────────┬──────────┘    │
│       │              │                 │               │
│  ┌────┴──────────────┴─────────────────┴──────────┐    │
│  │         Shared Dag instance (src/dag.py)       │    │
│  │         NetworkX DiGraph + JSON persistence    │    │
│  └────────────────────┬───────────────────────────┘    │
└───────────────────────┬───────────────────────────────┘
                        │
              ┌─────────┴──────────┐
              │  dag_state.json    │  (configurable path)
              └────────────────────┘
```

## 5. File Structure

```
agentic-dag/
├── src/
│   ├── __init__.py          # Package marker
│   ├── dag.py               # DAG model (NetworkX + JSON persistence)
│   ├── bot.py               # Telegram bot command handlers
│   ├── notifications.py     # Chat ID registry & pending reviews
│   ├── notify.py            # CLI notification sender
│   ├── visualize.py         # Mermaid diagram generation
│   ├── main.py              # Original bot entry point
│   ├── web.py               # ★ FastAPI backend (NEW)
│   ├── run_web.py           # ★ Web server entry point (NEW)
│   └── static/
│       └── index.html       # ★ Single-page frontend (NEW)
├── docs/
│   └── PRD.md               # This file
├── requirements.txt         # Updated with fastapi, uvicorn
└── dag_state.json           # Default DAG persistence file
```

## 6. Backend API Contract

### 6.1 Configuration

| Method | Endpoint | Body/Query | Response | Description |
|--------|----------|------------|----------|-------------|
| `GET` | `/api/config/state-file` | — | `{"path": "..."}` | Current DAG state file path |
| `PUT` | `/api/config/state-file` | `{"path": "..."}` | `{"path": "...", "status": "ok"}` | Change state file at runtime |

### 6.2 DAG Operations

| Method | Endpoint | Body/Query | Response | Description |
|--------|----------|------------|----------|-------------|
| `GET` | `/api/dag` | — | `{"nodes": [...], "edges": [...]}` | Full DAG data |
| `GET` | `/api/dag/mermaid` | — | Mermaid text | Mermaid flowchart syntax |
| `POST` | `/api/dag/nodes` | `{"id": "...", "label": "..."}` | `{"status": "ok"}` | Add node |
| `PUT` | `/api/dag/nodes/{id}` | `{"label": "..."}` | `{"status": "ok"}` | Update node label |
| `DELETE` | `/api/dag/nodes/{id}` | — | `{"status": "ok"}` | Delete node + edges |
| `POST` | `/api/dag/edges` | `{"source": "...", "target": "..."}` | `{"status": "ok"}` | Add edge (cycle-checked) |
| `DELETE` | `/api/dag/edges` | `?source=...&target=...` | `{"status": "ok"}` | Delete edge |

### 6.3 Telegram Bot Control

| Method | Endpoint | Body | Response | Description |
|--------|----------|------|----------|-------------|
| `GET` | `/api/telegram/status` | — | `{"running": bool, "chat_ids": [...], "pending_reviews_count": int}` | Bot status |
| `POST` | `/api/telegram/start` | — | `{"status": "ok"}` | Start bot in background thread |
| `POST` | `/api/telegram/stop` | — | `{"status": "ok"}` | Stop bot gracefully |
| `GET` | `/api/telegram/chats` | — | `[chat_id, ...]` | List registered chats |
| `DELETE` | `/api/telegram/chats/{id}` | — | `{"status": "ok"}` | Unregister a chat |
| `POST` | `/api/telegram/notify` | `{"node_id": "...", "message": "..."}` | `{"status": "ok"}` | Send notification |

## 7. Frontend Specification

### 7.1 Layout

- **Header**: App title + Telegram bot status indicator (green/red dot) + Start/Stop button
- **Main area** (two columns):
  - **Left (60%)**: D3.js force-directed DAG visualization
  - **Right (40%)**: Tabbed control panel (Nodes / Edges / Telegram / Settings)
- **Bottom bar**: Status text + last refresh timestamp
- **Toast notifications**: Slide-in from bottom-right for success/error feedback

### 7.2 DAG Visualization (D3.js)

- Force-directed layout with `d3.forceSimulation`
- Nodes: rounded rectangles (`<rect>` with `rx`/`ry`) colored by status
- Edges: directed paths with arrowhead markers
- Interactions: drag, zoom/pan, click-to-select, right-click context menu
- Status color mapping from label prefix (before ` — `):
  - In Progress → `#0984e3` (blue)
  - To Do → `#fdcb6e` (amber)
  - Review → `#6c5ce7` (purple)
  - Done → `#00b894` (green)
  - Backlog → `#b2bec3` (gray)
  - Archived → `#636e72` (dark gray)
  - Default → `#74b9ff` (steel blue)
- Auto-refreshes every 5 seconds, preserving node positions

### 7.3 Nodes Tab

- Add node form (ID + Label)
- Searchable node list with Edit / Delete buttons

### 7.4 Edges Tab

- Add edge form (Source dropdown + Target dropdown)
- Edge list with Delete buttons

### 7.5 Telegram Tab

- Bot status with Start/Stop toggle
- Pending reviews count
- Send notification form (Node dropdown + Message textarea)
- Registered chat IDs list with Remove buttons

### 7.6 Settings Tab

- **DAG State File**: Input field for the JSON file path
  - "Apply" button sends `PUT /api/config/state-file` and saves to `localStorage`
  - "Reset to Default" button clears `localStorage` and reverts to server startup default
  - On page load: restores saved path from `localStorage` and pushes it to the backend
- **Recent Files**: List of recently used file paths (max 10, stored in `localStorage`)
  - Click any entry to instantly switch to that file

### 7.7 localStorage Keys

| Key | Type | Description |
|-----|------|-------------|
| `dag_state_file_path` | `string` | Last applied DAG state file path |
| `dag_recent_files` | `string[]` (JSON) | Up to 10 most recently used file paths |

### 7.8 Color Theme (Dark)

```css
--bg-primary: #1a1b2e;
--bg-secondary: #252641;
--bg-tertiary: #2d2f4e;
--text-primary: #e8e8f0;
--text-secondary: #a0a0b8;
--accent: #6c5ce7;
--success: #00b894;
--warning: #fdcb6e;
--danger: #e17055;
--border: #3a3b5c;
```

## 8. Running the Web UI

```bash
# Install dependencies
pip install -r requirements.txt

# Start the web server
python -m src.run_web

# Open in browser
# http://localhost:8080
```

The web server runs on port **8080** by default. The Telegram bot can be started/stopped from the UI without needing a separate terminal.

## 9. Technical Notes

- **Single Dag instance**: Both the web API and the Telegram bot (when running) share the same `Dag` object. The web API calls `dag.load()` before reads to pick up any changes the bot has made.
- **Telegram bot threading**: The bot runs in a daemon thread with its own asyncio event loop. Start/stop is managed via `TelegramBotManager`.
- **NetworkX compatibility**: The API handles both `"links"` (older NetworkX) and `"edges"` (newer NetworkX ≥3.x) keys in `node_link_data()` output.
- **CORS**: Enabled for all origins to support development.
- **Static files**: Served at `/` with `html=True` mode for SPA routing.

## 10. Future Improvements

- [ ] Node metadata editing (beyond just label)
- [ ] Bulk import/export via UI
- [ ] Authentication/authorization for production use
- [ ] WebSocket-based real-time updates (replace polling)
- [ ] Persistent node positions (save layout coordinates)
- [ ] Dark/light theme toggle
- [ ] Mobile-responsive layout improvements
