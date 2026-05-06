"""Tests for SSE client."""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock


class TestSSEClient:
    def test_init(self):
        from sse_client import SSEClient
        client = SSEClient("http://localhost:8001/api/stream")
        assert client.url == "http://localhost:8001/api/stream"
        assert client._running is False
        assert client._reconnect_delay == 1.0

    def test_reconnect_delay_initial_value(self):
        from sse_client import SSEClient
        client = SSEClient("http://localhost:8001/api/stream")
        assert client._reconnect_delay == 1.0
        assert client._max_delay == 30.0