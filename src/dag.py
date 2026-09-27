import json
import os
from datetime import datetime, timezone

import networkx as nx

DEFAULT_STATE_FILE = os.path.join(os.path.dirname(__file__), '..', 'dag_state.json')


class Dag:
    def __init__(self, state_file: str | None = None):
        self.state_file = state_file or os.getenv('DAG_STATE_FILE', DEFAULT_STATE_FILE)
        self.graph = nx.DiGraph()
        self.load()

    def _extract_clean_title(self, node: dict, fallback_id: str = "") -> str:
        title = node.get("deck", {}).get("card", {}).get("title")
        if not title:
            title = node.get("label", fallback_id)
            for prefix in ("Backlog — ", "To Do — ", "In Progress — ", "Review — ", "Done — ", "Archived — "):
                title = title.removeprefix(prefix)
            title = title.split(" — Approved:")[0].split(" — Changes requested:")[0].split(" — Review response:")[0]
        return title.strip() or fallback_id

    def get_node_status(self, node_id: str) -> str:
        if node_id not in self.graph:
            raise ValueError(f"Node {node_id} does not exist")
        node = self.graph.nodes[node_id]
        label = node.get("label", "")
        for status in ("Backlog", "To Do", "In Progress", "Review", "Done", "Archived"):
            if label.startswith(f"{status} —") or label == status:
                return status
        return node.get("checkpoint", {}).get("status", "To Do")

    def set_node_status(self, node_id: str, status: str):
        if node_id not in self.graph:
            raise ValueError(f"Node {node_id} does not exist")
        node = self.graph.nodes[node_id]
        title = self._extract_clean_title(node, fallback_id=node_id)
        node["label"] = f"{status} — {title}"
        if "checkpoint" in node:
            node["checkpoint"]["status"] = status
            node["checkpoint"]["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.save()

    def update_checkpoint(
        self,
        node_id: str,
        status: str | None = None,
        findings: str | None = None,
        artifacts: list[str] | str | None = None,
        next_step: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        if node_id not in self.graph:
            raise ValueError(f"Node {node_id} does not exist")
        node = self.graph.nodes[node_id]
        checkpoint = node.setdefault("checkpoint", {})
        if findings is not None:
            checkpoint["findings"] = findings
        if artifacts is not None:
            if isinstance(artifacts, str):
                artifacts = [a.strip() for a in artifacts.split(",") if a.strip()]
            checkpoint["artifacts"] = artifacts
        if next_step is not None:
            checkpoint["next_step"] = next_step
        if metadata:
            checkpoint.setdefault("metadata", {}).update(metadata)
        checkpoint["updated_at"] = datetime.now(timezone.utc).isoformat()

        if status:
            checkpoint["status"] = status
            title = self._extract_clean_title(node, fallback_id=node_id)
            node["label"] = f"{status} — {title}"

        self.save()
        return checkpoint

    def get_unblocked_nodes(self) -> list[dict]:
        """Return nodes that are ready to run (predecessors are all Done or Archived)."""
        unblocked = []
        for node_id in self.graph.nodes:
            status = self.get_node_status(node_id)
            if status in ("Done", "Archived"):
                continue
            predecessors = list(self.graph.predecessors(node_id))
            preds_done = all(self.get_node_status(p) in ("Done", "Archived") for p in predecessors)
            if preds_done:
                node_data = dict(self.graph.nodes[node_id])
                node_data["id"] = node_id
                node_data["status"] = status
                node_data["title"] = self._extract_clean_title(node_data, fallback_id=node_id)
                node_data["dependencies"] = predecessors
                unblocked.append(node_data)
        return unblocked

    def get_next_actionable_node(self) -> dict | None:
        """Return the active In Progress node if any, otherwise first unblocked To Do node."""
        unblocked = self.get_unblocked_nodes()
        for node in unblocked:
            if node.get("status") == "In Progress":
                return node
        for node in unblocked:
            if node.get("status") == "To Do":
                return node
        return unblocked[0] if unblocked else None

    def add_node(self, node_id: str, label: str = "", checkpoint: dict | None = None):
        if node_id in self.graph:
            raise ValueError(f"Node {node_id} already exists")
        kwargs = {"label": label}
        if checkpoint:
            kwargs["checkpoint"] = checkpoint
        self.graph.add_node(node_id, **kwargs)
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
        title = self._extract_clean_title(node, fallback_id=node_id)
        summary = " ".join(response.split())[:180]
        node.setdefault("review_responses", []).append({
            "chat_id": chat_id,
            "received_at": datetime.now(timezone.utc).isoformat(),
            "response": response,
            "status": status,
        })
        node["label"] = f"{status} — {title} — {decision}: {summary}"
        if "checkpoint" in node:
            node["checkpoint"]["status"] = status
            node["checkpoint"]["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.save()
        return status

    def to_dict(self):
        return nx.readwrite.json_graph.node_link_data(self.graph)

    def save(self):
        with open(self.state_file, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    def load(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file) as f:
                    content = f.read().strip()
                    if content:
                        data = json.loads(content)
                        self.graph = nx.readwrite.json_graph.node_link_graph(data)
                    else:
                        self.graph = nx.DiGraph()
            except (json.JSONDecodeError, ValueError):
                self.graph = nx.DiGraph()
        else:
            self.graph = nx.DiGraph()

    def __str__(self):
        return "\n".join([f"{n}: {self.graph.nodes[n].get('label','')}" for n in self.graph.nodes])
