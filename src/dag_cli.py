import argparse
import json
import sys
from .dag import Dag


def format_node_summary(node: dict) -> str:
    node_id = node.get("id", "")
    status = node.get("status", "")
    title = node.get("title", node.get("label", ""))
    checkpoint = node.get("checkpoint", {})
    output = [
        f"Node ID: {node_id}",
        f"Status:  {status}",
        f"Title:   {title}",
    ]
    if "dependencies" in node:
        output.append(f"Depends on: {', '.join(node['dependencies']) if node['dependencies'] else '(none)'}")
    if checkpoint:
        if checkpoint.get("findings"):
            output.append(f"Findings: {checkpoint['findings']}")
        if checkpoint.get("artifacts"):
            artifacts_str = ", ".join(checkpoint['artifacts']) if isinstance(checkpoint['artifacts'], list) else str(checkpoint['artifacts'])
            output.append(f"Artifacts: {artifacts_str}")
        if checkpoint.get("next_step"):
            output.append(f"Next step: {checkpoint['next_step']}")
        if checkpoint.get("updated_at"):
            output.append(f"Updated at: {checkpoint['updated_at']}")
    return "\n".join(output)


def cmd_next(dag: Dag, args):
    node = dag.get_next_actionable_node()
    if not node:
        if args.json:
            print(json.dumps({"status": "no_actionable_nodes"}))
        else:
            print("No actionable (unblocked) tasks found in DAG.")
        return 0

    if args.json:
        print(json.dumps(node, indent=2))
    else:
        print(format_node_summary(node))
    return 0


def cmd_checkpoint(dag: Dag, args):
    checkpoint = dag.update_checkpoint(
        node_id=args.node_id,
        status=args.status,
        findings=args.findings,
        artifacts=args.artifacts,
        next_step=args.next,
    )
    if args.json:
        print(json.dumps({"node_id": args.node_id, "checkpoint": checkpoint}, indent=2))
    else:
        print(f"Checkpoint saved for node '{args.node_id}'. Status: {dag.get_node_status(args.node_id)}")
    return 0


def cmd_complete(dag: Dag, args):
    checkpoint = dag.update_checkpoint(
        node_id=args.node_id,
        status="Done",
        findings=args.findings,
        artifacts=args.artifacts,
        next_step="(Completed)",
    )
    if args.json:
        print(json.dumps({"node_id": args.node_id, "status": "Done", "checkpoint": checkpoint}, indent=2))
    else:
        print(f"Node '{args.node_id}' marked as Done.")
    return 0


def cmd_list(dag: Dag, args):
    nodes_data = []
    for node_id in dag.graph.nodes:
        status = dag.get_node_status(node_id)
        if not args.all and status in ("Done", "Archived"):
            continue
        node = dict(dag.graph.nodes[node_id])
        node["id"] = node_id
        node["status"] = status
        node["title"] = dag._extract_clean_title(node, fallback_id=node_id)
        node["dependencies"] = list(dag.graph.predecessors(node_id))
        nodes_data.append(node)

    if args.json:
        print(json.dumps(nodes_data, indent=2))
    else:
        if not nodes_data:
            print("No active nodes in DAG.")
            return 0
        for node in nodes_data:
            deps = f" [depends on: {', '.join(node['dependencies'])}]" if node['dependencies'] else ""
            print(f"- [{node['status']}] {node['id']}: {node['title']}{deps}")
    return 0


def cmd_show(dag: Dag, args):
    if args.node_id not in dag.graph:
        print(f"Error: Node '{args.node_id}' not found.", file=sys.stderr)
        return 1
    node_data = dict(dag.graph.nodes[args.node_id])
    node_data["id"] = args.node_id
    node_data["status"] = dag.get_node_status(args.node_id)
    node_data["title"] = dag._extract_clean_title(node_data, fallback_id=args.node_id)
    node_data["dependencies"] = list(dag.graph.predecessors(args.node_id))
    if args.json:
        print(json.dumps(node_data, indent=2))
    else:
        print(format_node_summary(node_data))
    return 0


def cmd_add(dag: Dag, args):
    status = args.status or "To Do"
    label = f"{status} — {args.title}"
    dag.add_node(args.node_id, label=label)
    if args.depends_on:
        deps = [d.strip() for d in args.depends_on.split(",") if d.strip()]
        for dep in deps:
            dag.add_edge(dep, args.node_id)
    if args.json:
        print(json.dumps({"node_id": args.node_id, "label": label, "status": "ok"}, indent=2))
    else:
        print(f"Created node '{args.node_id}' with status '{status}'.")
    return 0


def main(argv=None):
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument("--json", action="store_true", help="Output results in JSON format")

    parser = argparse.ArgumentParser(
        prog="python -m src.dag_cli",
        description="Agentic DAG Checkpoint and Task Memory CLI",
        parents=[common_parser],
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # next
    parser_next = subparsers.add_parser("next", parents=[common_parser], help="Get the next actionable / unblocked task")
    parser_next.set_defaults(func=cmd_next)

    # checkpoint
    parser_cp = subparsers.add_parser("checkpoint", parents=[common_parser], help="Record progress / context checkpoint to a node")
    parser_cp.add_argument("node_id", help="Target node ID")
    parser_cp.add_argument("--status", choices=["Backlog", "To Do", "In Progress", "Review", "Done", "Archived"], help="Update node status")
    parser_cp.add_argument("--findings", help="Key findings, bug hypotheses, or intermediate results")
    parser_cp.add_argument("--artifacts", help="Comma-separated list of working files/artifacts modified")
    parser_cp.add_argument("--next", help="Concrete next immediate step to execute after resume/compaction")
    parser_cp.set_defaults(func=cmd_checkpoint)

    # complete
    parser_done = subparsers.add_parser("complete", parents=[common_parser], help="Mark a node as Done")
    parser_done.add_argument("node_id", help="Node ID to mark as Done")
    parser_done.add_argument("--findings", help="Final summary / resolution findings")
    parser_done.add_argument("--artifacts", help="Comma-separated list of final artifacts")
    parser_done.set_defaults(func=cmd_complete)

    # list
    parser_list = subparsers.add_parser("list", parents=[common_parser], help="List DAG nodes and their blockers")
    parser_list.add_argument("--all", action="store_true", help="Include Done and Archived tasks")
    parser_list.set_defaults(func=cmd_list)

    # show
    parser_show = subparsers.add_parser("show", parents=[common_parser], help="Show details and checkpoint of a specific node")
    parser_show.add_argument("node_id", help="Node ID to display")
    parser_show.set_defaults(func=cmd_show)

    # add
    parser_add = subparsers.add_parser("add", parents=[common_parser], help="Add a new node to the DAG")
    parser_add.add_argument("node_id", help="Unique ID for the node")
    parser_add.add_argument("title", help="Task title / description")
    parser_add.add_argument("--status", default="To Do", choices=["Backlog", "To Do", "In Progress", "Review", "Done", "Archived"])
    parser_add.add_argument("--depends-on", help="Comma-separated list of prerequisite node IDs")
    parser_add.set_defaults(func=cmd_add)

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0

    dag = Dag()
    return args.func(dag, args)


if __name__ == "__main__":
    sys.exit(main())
