import io
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch
from src.dag_cli import main


class TestDagCli(unittest.TestCase):
    def setUp(self):
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        self.temp_file.close()
        self.original_env = os.environ.copy()
        os.environ["DAG_STATE_FILE"] = self.temp_file.name

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.original_env)
        if os.path.exists(self.temp_file.name):
            os.remove(self.temp_file.name)

    def test_cli_lifecycle(self):
        # 1. Add node 1
        ret = main(["add", "t-1", "Setup DB schema", "--status", "To Do"])
        self.assertEqual(ret, 0)

        # 2. Add node 2 depending on node 1
        ret = main(["add", "t-2", "Implement API endpoints", "--depends-on", "t-1"])
        self.assertEqual(ret, 0)

        # 3. Query next unblocked task
        with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            ret = main(["next", "--json"])
            self.assertEqual(ret, 0)
            data = json.loads(mock_out.getvalue())
            self.assertEqual(data["id"], "t-1")
            self.assertEqual(data["status"], "To Do")

        # 4. Checkpoint node 1
        ret = main([
            "checkpoint", "t-1",
            "--status", "In Progress",
            "--findings", "Schema drafted",
            "--artifacts", "schema.sql",
            "--next", "Run migrations",
        ])
        self.assertEqual(ret, 0)

        # 5. Complete node 1
        ret = main(["complete", "t-1", "--findings", "Migrations passed"])
        self.assertEqual(ret, 0)

        # 6. Next unblocked task is now t-2
        with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            ret = main(["next", "--json"])
            self.assertEqual(ret, 0)
            data = json.loads(mock_out.getvalue())
            self.assertEqual(data["id"], "t-2")


if __name__ == "__main__":
    unittest.main()
