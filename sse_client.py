"""SSE client with automatic reconnection for System Monitor."""
import asyncio
import httpx
import logging
from typing import Optional, Callable, Awaitable

logger = logging.getLogger(__name__)


class SSEClient:
    """SSE client supporting automatic reconnection with exponential backoff."""

    def __init__(self, url: str):
        self.url = url
        self._client: Optional[httpx.AsyncClient] = None
        self._reconnect_delay: float = 1.0
        self._max_delay: float = 30.0
        self._max_retries: int = 0  # 0 = infinite
        self._running: bool = False
        self._on_message: Optional[Callable[[dict], Awaitable[None]]] = None
        self._on_connect: Optional[Callable[[], Awaitable[None]]] = None
        self._on_disconnect: Optional[Callable[[], Awaitable[None]]] = None

    async def connect(
        self,
        on_message: Callable[[dict], Awaitable[None]],
        on_connect: Optional[Callable[[], Awaitable[None]]] = None,
        on_disconnect: Optional[Callable[[], Awaitable[None]]] = None,
    ):
        """Connect to SSE stream with automatic reconnection."""
        self._on_message = on_message
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect
        self._running = True
        self._reconnect_delay = 1.0

        while self._running:
            try:
                await self._connect_once()
            except asyncio.CancelledError:
                break
            except Exception as e:
                if not self._running:
                    break
                logger.warning(f"SSE connection error: {e}, reconnecting in {self._reconnect_delay}s")
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2, self._max_delay)

    async def _connect_once(self):
        """Single SSE connection attempt."""
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
            self._client = client
            async with client.stream("GET", self.url) as response:
                response.raise_for_status()
                if self._on_connect:
                    await self._on_connect()
                self._reconnect_delay = 1.0  # reset on successful connection

                async for line in response.aiter_lines():
                    if not self._running:
                        break
                    if line.startswith("data: "):
                        data_str = line[6:]  # strip "data: "
                        if data_str.startswith(": heartbeat"):
                            continue
                        if data_str.strip():
                                import json
                                try:
                                    data = json.loads(data_str)
                                    if self._on_message:
                                        await self._on_message(data)
                                except json.JSONDecodeError:
                                    logger.warning(f"Invalid JSON in SSE data: {data_str}")

    async def disconnect(self):
        """Gracefully disconnect from SSE stream."""
        self._running = False
        if self._client:
            await self._client.aclose()
            self._client = None