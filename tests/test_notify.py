import unittest
from unittest.mock import AsyncMock, patch
import asyncio
import os
import sys

from src.notify import main as notify_main, send_notification
from src.run_web import find_listening_socket
from src.web import NotifyModel


class TestNotify(unittest.TestCase):
    def setUp(self):
        self.original_env = os.environ.copy()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.original_env)

    @patch("src.notify.notification_chat_ids", return_value=[12345])
    @patch("src.notify.register_pending_review")
    @patch("src.notify.Bot")
    def test_send_notification_without_project_title(self, mock_bot_cls, mock_register, mock_chat_ids):
        os.environ["TELEGRAM_BOT_TOKEN"] = "fake_token"
        os.environ.pop("PROJECT_TITLE", None)

        mock_bot_instance = AsyncMock()
        mock_bot_cls.return_value.__aenter__.return_value = mock_bot_instance

        sent_msg = AsyncMock()
        sent_msg.message_id = 99
        mock_bot_instance.send_message.return_value = sent_msg

        asyncio.run(send_notification("task-1", "Please review code"))

        mock_bot_instance.send_message.assert_called_once_with(
            chat_id=12345,
            text="Review needed for task-1\n\nPlease review code\n\nReply directly to this message with approved, rejected, or your review notes."
        )

    @patch("src.notify.notification_chat_ids", return_value=[12345])
    @patch("src.notify.register_pending_review")
    @patch("src.notify.Bot")
    def test_send_notification_with_project_title_env(self, mock_bot_cls, mock_register, mock_chat_ids):
        os.environ["TELEGRAM_BOT_TOKEN"] = "fake_token"
        os.environ["PROJECT_TITLE"] = "My Awesome Project"

        mock_bot_instance = AsyncMock()
        mock_bot_cls.return_value.__aenter__.return_value = mock_bot_instance

        sent_msg = AsyncMock()
        sent_msg.message_id = 99
        mock_bot_instance.send_message.return_value = sent_msg

        asyncio.run(send_notification("task-1", "Please review code"))

        mock_bot_instance.send_message.assert_called_once_with(
            chat_id=12345,
            text="Project: My Awesome Project\nReview needed for task-1\n\nPlease review code\n\nReply directly to this message with approved, rejected, or your review notes."
        )

    @patch("src.notify.notification_chat_ids", return_value=[12345])
    @patch("src.notify.register_pending_review")
    @patch("src.notify.Bot")
    def test_send_notification_with_project_title_param(self, mock_bot_cls, mock_register, mock_chat_ids):
        os.environ["TELEGRAM_BOT_TOKEN"] = "fake_token"
        os.environ["PROJECT_TITLE"] = "Env Title"

        mock_bot_instance = AsyncMock()
        mock_bot_cls.return_value.__aenter__.return_value = mock_bot_instance

        sent_msg = AsyncMock()
        sent_msg.message_id = 99
        mock_bot_instance.send_message.return_value = sent_msg

        # Explicit parameter should override env title
        asyncio.run(send_notification("task-1", "Please review code", project_title="Custom Param Title"))

        mock_bot_instance.send_message.assert_called_once_with(
            chat_id=12345,
            text="Project: Custom Param Title\nReview needed for task-1\n\nPlease review code\n\nReply directly to this message with approved, rejected, or your review notes."
        )

    def test_web_notify_model(self):
        model = NotifyModel(node_id="node-123", message="msg", project_title="Web Title")
        self.assertEqual(model.project_title, "Web Title")
        self.assertTrue(model.wait)

    @patch("src.run_web.socket.socket")
    def test_web_runner_binds_only_to_loopback(self, mock_socket):
        socket_instance = mock_socket.return_value
        server_socket, port = find_listening_socket(18180, attempts=1)
        self.assertIs(server_socket, socket_instance)
        self.assertEqual(port, 18180)
        socket_instance.bind.assert_called_once_with(("127.0.0.1", 18180))

    @patch("src.notify.wait_for_review", return_value={"status": "In Progress"})
    @patch("src.notify.send_notification", new_callable=AsyncMock)
    @patch.object(sys, "argv", ["notify", "task-1", "Please review"])
    def test_cli_waits_by_default(self, mock_send, mock_wait):
        asyncio.run(notify_main())
        mock_send.assert_awaited_once_with("task-1", "Please review", project_title=None)
        mock_wait.assert_called_once_with("task-1", timeout=300)

    @patch("src.notify.wait_for_review")
    @patch("src.notify.send_notification", new_callable=AsyncMock)
    @patch.object(sys, "argv", ["notify", "task-1", "Please review", "--no-wait"])
    def test_cli_can_opt_out_of_waiting(self, mock_send, mock_wait):
        asyncio.run(notify_main())
        mock_send.assert_awaited_once_with("task-1", "Please review", project_title=None)
        mock_wait.assert_not_called()

    def test_default_registry_path(self):
        from src.notifications import DEFAULT_REGISTRY_PATH
        from pathlib import Path
        expected_root = Path(__file__).resolve().parents[1]
        self.assertEqual(DEFAULT_REGISTRY_PATH, expected_root / "telegram_notification_chat_ids.json")

    def test_project_root_dynamic(self):
        from src.web import PROJECT_ROOT
        from pathlib import Path
        expected_root = str(Path(__file__).resolve().parents[1])
        self.assertEqual(PROJECT_ROOT, expected_root)


if __name__ == "__main__":
    unittest.main()
