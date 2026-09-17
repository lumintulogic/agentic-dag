import unittest
from unittest.mock import AsyncMock, patch
import os
import asyncio

from src.notify import send_notification
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


if __name__ == "__main__":
    unittest.main()
