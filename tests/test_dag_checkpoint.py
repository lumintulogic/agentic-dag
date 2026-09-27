import os
import tempfile
import unittest
from src.dag import Dag


class TestDagCheckpoint(unittest.TestCase):
    def setUp(self):
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        self.temp_file.close()
        self.dag = Dag(state_file=self.temp_file.name)

    def tearDown(self):
        if os.path.exists(self.temp_file.name):
            os.remove(self.temp_file.name)

    def test_checkpoint_roundtrip(self):
        self.dag.add_node("task-1", "To Do — Implement authentication")
        self.assertEqual(self.dag.get_node_status("task-1"), "To Do")

        self.dag.update_checkpoint(
            node_id="task-1",
            status="In Progress",
            findings="Identified token expiration bug",
            artifacts=["src/auth.py", "tests/test_auth.py"],
            next_step="Write refresh token rotation logic",
        )

        # Reload DAG from disk
        reloaded = Dag(state_file=self.temp_file.name)
        self.assertEqual(reloaded.get_node_status("task-1"), "In Progress")
        node_data = reloaded.graph.nodes["task-1"]
        self.assertIn("checkpoint", node_data)
        cp = node_data["checkpoint"]
        self.assertEqual(cp["findings"], "Identified token expiration bug")
        self.assertEqual(cp["artifacts"], ["src/auth.py", "tests/test_auth.py"])
        self.assertEqual(cp["next_step"], "Write refresh token rotation logic")
        self.assertEqual(cp["status"], "In Progress")

    def test_unblocked_nodes_and_next_actionable(self):
        self.dag.add_node("task-1", "To Do — Step 1")
        self.dag.add_node("task-2", "To Do — Step 2")
        self.dag.add_node("task-3", "To Do — Step 3")
        self.dag.add_edge("task-1", "task-2")
        self.dag.add_edge("task-2", "task-3")

        # Initially, only task-1 is unblocked
        unblocked = self.dag.get_unblocked_nodes()
        unblocked_ids = [n["id"] for n in unblocked]
        self.assertEqual(unblocked_ids, ["task-1"])

        next_node = self.dag.get_next_actionable_node()
        self.assertIsNotNone(next_node)
        self.assertEqual(next_node["id"], "task-1")

        # Start task-1
        self.dag.update_checkpoint("task-1", status="In Progress")
        next_node = self.dag.get_next_actionable_node()
        self.assertEqual(next_node["id"], "task-1")
        self.assertEqual(next_node["status"], "In Progress")

        # Mark task-1 Done -> task-2 becomes unblocked
        self.dag.update_checkpoint("task-1", status="Done")
        unblocked = self.dag.get_unblocked_nodes()
        unblocked_ids = [n["id"] for n in unblocked]
        self.assertEqual(unblocked_ids, ["task-2"])

        next_node = self.dag.get_next_actionable_node()
        self.assertEqual(next_node["id"], "task-2")


if __name__ == "__main__":
    unittest.main()
