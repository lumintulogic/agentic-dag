import json
import os
import networkx as nx

STATE_FILE = os.path.join(os.path.dirname(__file__), '..', 'dag_state.json')

class Dag:
    def __init__(self):
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

    def to_dict(self):
        return nx.readwrite.json_graph.node_link_data(self.graph)

    def save(self):
        with open(STATE_FILE, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    def load(self):
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE) as f:
                data = json.load(f)
                self.graph = nx.readwrite.json_graph.node_link_graph(data)
        else:
            self.graph = nx.DiGraph()

    def __str__(self):
        return "\n".join([f"{n}: {self.graph.nodes[n].get('label','')}" for n in self.graph.nodes])

