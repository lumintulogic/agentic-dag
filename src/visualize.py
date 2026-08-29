import networkx as nx

def generate_mermaid(dag):
    """Return a Mermaid flowchart representation of the given Dag instance.
    The Dag object is expected to have a `graph` attribute which is a networkx DiGraph.
    Nodes use the 'label' attribute for display.
    """
    lines = ["flowchart TD"]
    for node, data in dag.graph.nodes(data=True):
        label = data.get('label', node)
        # Escape special characters for Mermaid node label
        safe_label = str(label).replace('"', '\\"')
        lines.append(f'    {node}["{safe_label}"]')
    for src, dst in dag.graph.edges():
        lines.append(f'    {src} --> {dst}')
    return "\n".join(lines)

