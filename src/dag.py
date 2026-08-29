import json
import os
from datetime import datetime, timezone

import networkx as nx

DEFAULT_STATE_FILE = os.path.join(os.path.dirname(__file__), '..', 'dag_state.json')


class Dag:
    def __init__(self):
        self.state_file = os.getenv('DAG_STATE_FILE', DEFAULT_STATE_FILE)
        self.graph = nx.DiGraph()
        self.load()

    def add_node(self, node_id: str, label: str = ""):
        if node_id in self.graph:
            raise ValueError(f"Node {node_id} already exists")
        self.graph.add_node(node_id, label=label)
        self.save()

    def add_edge(self, from_id: str, to_id: str):
        self.graph.add_edge(from_id, to_id)
        if not nx.is_directed_acyclic_graph(self.graph):
            self.graph.remove_edge(from_id, to_id)
            raise ValueError("Adding this edge would create a cycle")
        self.save()

    def record_review_response(self, node_id: str, response: str, chat_id: int) -> str:
        if node_id not in self.graph:
            raise ValueError(f"Node {node_id} does not exist")
        normalized = response.strip().lower()
        if normalized.startswith(("approve", "approved", "yes", "go ahead", "proceed", "continue")):
            status = "In Progress"
            decision = "Approved"
        elif normalized.startswith(("reject", "rejected", "no", "changes requested", "revise")):
            status = "To Do"
            decision = "Changes requested"
        else:
            status = "Review"
            decision = "Review response"

        node = self.graph.nodes[node_id]
        title = node.get("deck", {}).get("card", {}).get("title")
        if not title:
            title = node.get("label", node_id)
            for prefix in ("Backlog — ", "To Do — ", "In Progress — ", "Review — ", "Done — ", "Archived — "):
                title = title.removeprefix(prefix)
            title = title.split(" — Approved:")[0].split(" — Changes requested:")[0].split(" — Review response:")[0]
        summary = " ".join(response.split())[:180]
        node.setdefault("review_responses", []).append({
            "chat_id": chat_id,
            "received_at": datetime.now(timezone.utc).isoformat(),
            "response": response,
            "status": status,
        })
        node["label"] = f"{status} — {title} — {decision}: {summary}"
        self.save()
        return status

    def to_dict(self):
        return nx.readwrite.json_graph.node_link_data(self.graph)

    def save(self):
        with open(self.state_file, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    def load(self):
        if os.path.exists(self.state_file):
            with open(self.state_file) as f:
                data = json.load(f)
                self.graph = nx.readwrite.json_graph.node_link_graph(data)
        else:
            self.graph = nx.DiGraph()

    def __str__(self):
        return "\n".join([f"{n}: {self.graph.nodes[n].get('label','')}" for n in self.graph.nodes])
