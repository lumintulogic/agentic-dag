STATUS_CLASSES = {
    "in_progress": ("#0984e3", "in progress"),
    "to_do": ("#fdcb6e", "to do"),
    "review": ("#6c5ce7", "review"),
    "done": ("#00b894", "done"),
    "backlog": ("#b2bec3", "backlog"),
    "archived": ("#636e72", "archived"),
    "default": ("#74b9ff", "default"),
}

STATUS_ALIASES = {
    "in progress": "in_progress",
    "to do": "to_do",
    "next": "to_do",
    "review": "review",
    "to review": "review",
    "done": "done",
    "backlog": "backlog",
    "archived": "archived",
}


def _status_class(label):
    """Return the Mermaid CSS class for a label's leading status tag."""
    tag = str(label).split(" — ", 1)[0].strip().lower()
    return STATUS_ALIASES.get(tag, "default")

def generate_mermaid(dag):
    """Return a Mermaid flowchart representation of the given Dag instance.
    The Dag object is expected to have a `graph` attribute which is a networkx DiGraph.
    Nodes use the 'label' attribute for display.
    """
    lines = ["flowchart TD"]
    nodes_by_class = {name: [] for name in STATUS_CLASSES}
    for node, data in dag.graph.nodes(data=True):
        label = data.get('label', node)
        # Escape special characters for Mermaid node label
        safe_label = str(label).replace('"', '\\"')
        lines.append(f'    {node}["{safe_label}"]')
        nodes_by_class[_status_class(label)].append(node)
    for src, dst in dag.graph.edges():
        lines.append(f'    {src} --> {dst}')
    for class_name, (color, _) in STATUS_CLASSES.items():
        lines.append(f"    classDef {class_name} fill:{color},stroke:#e8e8f0,color:#ffffff")
        if nodes := nodes_by_class[class_name]:
            lines.append(f"    class {','.join(str(node) for node in nodes)} {class_name}")
    return "\n".join(lines)
