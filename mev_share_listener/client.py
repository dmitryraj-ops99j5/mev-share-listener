import asyncio
import logging
import httpx
from typing import Callable, Coroutine, Any, Optional
from mev_share_listener.parser import parse_sse_event
from mev_share_listener.models import MevShareEvent
from mev_share_listener.stats import StatsCollector

logger = logging.getLogger("mev_share_listener.client")

DEFAULT_ENDPOINT = "https://mev-share.flashbots.net"

class MevShareClient:
    """Maintains persistent SSE connection to MEV-Share with reconnect backoff."""

    def __init__(
        self,
        endpoint: str = DEFAULT_ENDPOINT,
        on_event: Optional[Callable[[MevShareEvent], Coroutine[Any, Any, None]]] = None,
        stats: Optional[StatsCollector] = None,
    ):
        self.endpoint = endpoint.rstrip("/")
        self.on_event = on_event
        self.stats = stats
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def listen(self):
        self._running = True
        backoff = 0.5
        headers = {
            "Accept": "text/event-stream",
            "User-Agent": "mev-share-listener/0.3",
        }

        while self._running:
            try:
                # Flashbots ping interval is ~15s. If nothing comes through for 45s, connection is dead
                timeout = httpx.Timeout(connect=10.0, read=45.0, write=10.0, pool=10.0)
                async with httpx.AsyncClient(timeout=timeout) as client:
                    logger.info("connecting to %s", self.endpoint)
                    async with client.stream("GET", self.endpoint, headers=headers) as resp:
                        if resp.status_code == 429:
                            logger.warning("rate limited (429), backing off for 10s")
                            await asyncio.sleep(10.0)
                            continue
                        
                        if resp.status_code != 200:
                            logger.warning("bad status %d, will retry", resp.status_code)
                            await asyncio.sleep(backoff)
                            backoff = min(backoff * 1.5, 30.0)
                            continue

                        logger.info("sse stream connected")
                        backoff = 0.5
                        
                        event_type = "message"
                        data_buffer = []

                        async for line in resp.aiter_lines():
                            if not self._running:
                                break
                            
                            # comments/ping keepalives
                            if line.startswith(":"):
                                if self.stats:
                                    self.stats.inc_pings()
                                continue

                            if not line:
                                if data_buffer:
                                    payload = "\n".join(data_buffer)
                                    data_buffer.clear()
                                    await self._dispatch(event_type, payload)
                                event_type = "message"
                                continue

                            if line.startswith("event:"):
                                event_type = line[6:].strip()
                            elif line.startswith("data:"):
                                data_buffer.append(line[5:].strip())

            except (httpx.TransportError, httpx.ReadTimeout, asyncio.TimeoutError) as err:
                if not self._running:
                    break
                logger.warning("connection lost (%s), reconnecting in %.1fs", err, backoff)
                if self.stats:
                    self.stats.inc_reconnects()
                await asyncio.sleep(backoff)
                backoff = min(backoff * 1.5, 30.0)
            except Exception as ex:
                logger.exception("unexpected error in stream loop: %s", ex)
                await asyncio.sleep(2.0)

    async def _dispatch(self, event_type: str, raw_data: str):
        if not raw_data:
            return
        # print("DEBUG dispatch raw:", raw_data[:80])
        try:
            event = parse_sse_event(raw_data)
            if not event:
                return
            if self.stats:
                self.stats.inc_events()
            if self.on_event:
                await self.on_event(event)
        except Exception as e:
            logger.debug("failed parsing event payload: %s", e)

    def stop(self):
        self._running = False
