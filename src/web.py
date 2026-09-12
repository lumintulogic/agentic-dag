from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import os
import threading
import asyncio
import subprocess
import sys

from .dag import Dag
from .visualize import generate_mermaid
from .notifications import _load_registry, _save_registry
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

# The control panel can start the Telegram bot itself, so its process must load
# the same .env configuration as the standalone bot entry point.
load_dotenv()

class TelegramBotManager:
    def __init__(self):
        self._thread = None
        self._app = None
        self._loop = None
        self._running = False
    
    @property
    def is_running(self):
        return self._running and self._thread is not None and self._thread.is_alive()
    
    def start(self, token: str, dag):
        if self.is_running:
            raise RuntimeError("Bot is already running")
        
        self._thread = threading.Thread(target=self._run, args=(token, dag), daemon=True)
        self._thread.start()
    
    def _run(self, token, dag):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._async_run(token, dag))
        finally:
            self._running = False
            self._loop.close()
    
    async def _async_run(self, token, dag):
        from .bot import start, register, review_reply, add_node, add_edge, show, visualize, export
        app = ApplicationBuilder().token(token).build()
        app.add_handler(CommandHandler('start', start))
        app.add_handler(CommandHandler('register', register))
        app.add_handler(CommandHandler('add_node', add_node))
        app.add_handler(CommandHandler('add_edge', add_edge))
        app.add_handler(CommandHandler('show', show))
        app.add_handler(CommandHandler('visualize', visualize))
        app.add_handler(CommandHandler('export', export))
        app.add_handler(MessageHandler(filters.REPLY & filters.TEXT, review_reply))
        
        self._app = app
        self._running = True
        
        async with app:
            await app.start()
            await app.updater.start_polling()
            while self._running:
                await asyncio.sleep(1)
            await app.updater.stop()
            await app.stop()
            await app.shutdown()
    
    def stop(self):
        if not self.is_running:
            raise RuntimeError("Bot is not running")
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

dag = Dag()
bot_manager = TelegramBotManager()

class NodeModel(BaseModel):
    id: str
    label: str = ""

class NodeUpdateModel(BaseModel):
    label: str

class EdgeModel(BaseModel):
    source: str
    target: str

class NotifyModel(BaseModel):
    node_id: str
    message: str

class StateFileModel(BaseModel):
    path: str


@app.get("/api/config/state-file")
def get_state_file():
    return {"path": os.path.abspath(dag.state_file)}

@app.put("/api/config/state-file")
def set_state_file(model: StateFileModel):
    path = model.path.strip()
    if not path:
        raise HTTPException(status_code=400, detail="Path cannot be empty")
    # Resolve to absolute path
    abs_path = os.path.abspath(path)
    dag.state_file = abs_path
    dag.load()
    return {"path": abs_path, "status": "ok"}


@app.get("/api/dag")
def get_dag():
    dag.load()
    data = dag.to_dict()
    nodes = data.get("nodes", [])
    raw_edges = data.get("links", data.get("edges", []))
    edges = [{"source": link["source"], "target": link["target"]} for link in raw_edges]
    return {"nodes": nodes, "edges": edges}

@app.get("/api/dag/mermaid", response_class=PlainTextResponse)
def get_dag_mermaid():
    dag.load()
    return generate_mermaid(dag)

@app.get("/visualize", include_in_schema=False)
@app.get("/visualize/", include_in_schema=False)
def show_mermaid_visualization():
    return FileResponse(os.path.join(static_dir, "visualize.html"))

@app.post("/api/dag/nodes")
def add_node(node: NodeModel):
    dag.load()
    try:
        dag.add_node(node.id, node.label)
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/dag/nodes/{node_id}")
def delete_node(node_id: str):
    dag.load()
    if node_id not in dag.graph:
        raise HTTPException(status_code=404, detail="Node not found")
    dag.graph.remove_node(node_id)
    dag.save()
    return {"status": "ok"}

@app.put("/api/dag/nodes/{node_id}")
def update_node(node_id: str, node: NodeUpdateModel):
    dag.load()
    if node_id not in dag.graph:
        raise HTTPException(status_code=404, detail="Node not found")
    dag.graph.nodes[node_id]["label"] = node.label
    dag.save()
    return {"status": "ok"}

@app.post("/api/dag/edges")
def add_edge(edge: EdgeModel):
    dag.load()
    if edge.source not in dag.graph or edge.target not in dag.graph:
        raise HTTPException(status_code=400, detail="Source or target node does not exist")
    try:
        dag.add_edge(edge.source, edge.target)
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/dag/edges")
def remove_edge(source: str = Query(...), target: str = Query(...)):
    dag.load()
    if dag.graph.has_edge(source, target):
        dag.graph.remove_edge(source, target)
        dag.save()
        return {"status": "ok"}
    raise HTTPException(status_code=404, detail="Edge not found")

@app.get("/api/telegram/status")
def get_telegram_status():
    registry = _load_registry()
    chats = registry.get("chat_ids", [])
    pending = len(registry.get("pending_reviews", {}))
    return {
        "running": bot_manager.is_running,
        "chat_ids": chats,
        "pending_reviews_count": pending
    }

@app.post("/api/telegram/start")
def start_bot():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise HTTPException(status_code=400, detail="TELEGRAM_BOT_TOKEN not set in environment")
    try:
        bot_manager.start(token, dag)
        return {"status": "ok"}
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/telegram/stop")
def stop_bot():
    try:
        bot_manager.stop()
        return {"status": "ok"}
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/telegram/chats")
def list_chats():
    registry = _load_registry()
    return registry.get("chat_ids", [])

@app.delete("/api/telegram/chats/{chat_id}")
def unregister_chat(chat_id: int):
    registry = _load_registry()
    if chat_id in registry.get("chat_ids", []):
        registry["chat_ids"].remove(chat_id)
        _save_registry(registry)
        return {"status": "ok"}
    raise HTTPException(status_code=404, detail="Chat not found")

@app.post("/api/telegram/notify")
def notify_all(model: NotifyModel):
    try:
        subprocess.run([sys.executable, "-m", "src.notify", model.node_id, model.message], cwd="/config/workspace/dag", check=True)
        return {"status": "ok"}
    except subprocess.CalledProcessError:
        raise HTTPException(status_code=500, detail="Failed to send notification")

static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
