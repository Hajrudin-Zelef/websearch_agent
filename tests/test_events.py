"""
Tests unitaires pour core/events.py.
"""

import unittest
import sys
import os
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.events import fire_webhook, _is_webhook_enabled, _get_webhook_url


class TestWebhookConfig(unittest.TestCase):

    @patch("core.events._get_setting", return_value=True)
    def test_webhook_enabled(self, mock_get):
        self.assertTrue(_is_webhook_enabled())

    @patch("core.events._get_setting", return_value=False)
    def test_webhook_disabled(self, mock_get):
        self.assertFalse(_is_webhook_enabled())

    @patch("core.events._get_setting", return_value="https://example.com/hook")
    def test_webhook_url(self, mock_get):
        self.assertEqual(_get_webhook_url(), "https://example.com/hook")

    @patch("core.events._get_setting", return_value="")
    def test_webhook_url_empty(self, mock_get):
        self.assertEqual(_get_webhook_url(), "")


class TestFireWebhook(unittest.TestCase):

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    @patch("core.events._get_webhook_url", return_value="")
    @patch("core.events._is_webhook_enabled", return_value=True)
    def test_no_url_does_nothing(self, mock_enabled, mock_url):
        self._run(fire_webhook("test.event", {"key": "value"}))

    @patch("core.events._is_webhook_enabled", return_value=False)
    def test_disabled_does_nothing(self, mock_enabled):
        self._run(fire_webhook("test.event", {"key": "value"}))

    @patch("core.events._get_webhook_url", return_value="https://example.com/hook")
    @patch("core.events._is_webhook_enabled", return_value=True)
    @patch("core.events.aiohttp.ClientSession")
    def test_sends_post_request(self, mock_session_cls, mock_enabled, mock_url):
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.post.return_value = mock_response
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = mock_session

        self._run(fire_webhook("chat.completed", {"request_id": "abc123"}))

        mock_session.post.assert_called_once()
        call_args = mock_session.post.call_args
        self.assertEqual(call_args[0][0], "https://example.com/hook")
        payload = call_args[1]["json"]
        self.assertEqual(payload["event"], "chat.completed")
        self.assertEqual(payload["data"]["request_id"], "abc123")
        self.assertIn("timestamp", payload)

    @patch("core.events._get_webhook_url", return_value="https://example.com/hook")
    @patch("core.events._is_webhook_enabled", return_value=True)
    @patch("core.events.aiohttp.ClientSession")
    def test_handles_timeout(self, mock_session_cls, mock_enabled, mock_url):
        mock_session = AsyncMock()
        mock_session.post.side_effect = asyncio.TimeoutError()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = mock_session

        self._run(fire_webhook("chat.completed", {"key": "val"}))

    @patch("core.events._get_webhook_url", return_value="https://example.com/hook")
    @patch("core.events._is_webhook_enabled", return_value=True)
    @patch("core.events.aiohttp.ClientSession")
    def test_handles_http_error(self, mock_session_cls, mock_enabled, mock_url):
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.post.return_value = mock_response
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = mock_session

        self._run(fire_webhook("chat.completed", {"key": "val"}))

    @patch("core.events._get_webhook_url", return_value="https://example.com/hook")
    @patch("core.events._is_webhook_enabled", return_value=True)
    @patch("core.events.aiohttp.ClientSession")
    def test_handles_connection_error(self, mock_session_cls, mock_enabled, mock_url):
        mock_session = AsyncMock()
        mock_session.post.side_effect = Exception("Connection refused")
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = mock_session

        self._run(fire_webhook("chat.completed", {"key": "val"}))


if __name__ == "__main__":
    unittest.main()
