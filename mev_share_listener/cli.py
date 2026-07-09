import argparse
import asyncio
import signal
import sys
import logging
from pathlib import Path
from typing import List

from mev_share_listener.client import MevShareClient, DEFAULT_ENDPOINT
from mev_share_listener.filters import EventFilter
from mev_share_listener.sinks import StdoutSink, JsonlSink, SocketSink, CompositeSink
from mev_share_listener.stats import StatsCollector

logger = logging.getLogger("mev_share_listener")

def clean_hex_list(raw_items: List[str]) -> List[str]:
    out = []
    for item in raw_items:
        for part in item.split(","):
            part = part.strip().lower()
            if part:
                out.append(part)
    return out

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mev-share-listener",
        description="Ingest, filter and forward Flashbots MEV-Share SSE events",
    )
    p.add_argument("--url", default=DEFAULT_ENDPOINT, help="MEV-Share SSE stream endpoint")
    p.add_argument(
        "--address",
        "-a",
        action="append",
        default=[],
        help="Filter by contract/target address (repeatable or comma-separated)",
    )
    p.add_argument(
        "--selector",
        "-s",
        action="append",
        default=[],
        help="Filter by 4-byte selector hex e.g. 0x3593564c (repeatable)",
    )
    p.add_argument("--jsonl", type=Path, default=None, help="Append matching events to JSONL file")
    p.add_argument("--socket", type=Path, default=None, help="Unix domain socket path to stream JSON lines")
    p.add_argument("--no-stdout", action="store_true", help="Suppress standard output")
    p.add_argument("--show-stats", action="store_true", help="Print event throughput stats every 10 seconds")
    p.add_argument("-v", "--verbose", action="store_true", help="Verbose debug logging")
    return p

async def run_app(args: argparse.Namespace):
    sinks_list = []
    
    if not args.no_stdout:
        sinks_list.append(StdoutSink())
    if args.jsonl:
        sinks_list.append(JsonlSink(args.jsonl))
    if args.socket:
        sinks_list.append(SocketSink(args.socket))
        
    sink = CompositeSink(sinks_list)
    await sink.setup()

    addresses = clean_hex_list(args.address)
    selectors = clean_hex_list(args.selector)
    event_filter = EventFilter(addresses=addresses, selectors=selectors)

    stats = StatsCollector() if args.show_stats else None

    async def handle_event(event):
        if event_filter.matches(event):
            if stats:
                stats.inc_matches()
            await sink.write(event)

    client = MevShareClient(endpoint=args.url, on_event=handle_event, stats=stats)

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _sig_handler():
        logger.info("shutdown signal received")
        client.stop()
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _sig_handler)
        except NotImplementedError:
            pass  # windows fallback

    stats_task = None
    if stats:
        stats_task = asyncio.create_task(stats.reporter_loop(interval=10.0))

    client_task = asyncio.create_task(client.listen())
    
    await stop_event.wait()
    
    if stats_task:
        stats_task.cancel()
    await client_task
    await sink.close()

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        level=level,
    )

    try:
        asyncio.run(run_app(args))
    except KeyboardInterrupt:
        return 130
    return 0
