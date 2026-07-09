import asyncio
import json
import os
import sys
from pathlib import Path
from typing import List, Optional, TextIO
from mev_share_listener.models import MevEvent


class TerminalSink:
    def __init__(self, color: bool = True):
        self.color = color

    def write(self, event: MevEvent):
        if not self.color:
            tx_info = f"txs={len(event.txs)} logs={len(event.logs)}"
            print(f"[event] {event.hash or '<no hash>'} {tx_info}")
            return

        hash_part = f"\033[1;33m{event.hash or '<no hash>'}\033[0m"
        details = []
        for tx in event.txs:
            if tx.to:
                details.append(f"to:\033[36m{tx.to[:10]}..\033[0m")
            if tx.selector:
                details.append(f"sel:\033[35m{tx.selector}\033[0m")
        for log in event.logs:
            if log.address:
                details.append(f"log:\033[32m{log.address[:10]}..\033[0m")
        
        joined = " ".join(details) if details else "empty hints"
        print(f"\033[90m>\033[0m {hash_part} {joined}")


class JsonlSink:
    def __init__(self, path: str, flush: bool = True):
        self.path = Path(path)
        self.flush = flush
        self._file: Optional[TextIO] = None

    def start(self):
        self._file = open(self.path, "a", encoding="utf-8")

    def write(self, event: MevEvent):
        if not self._file:
            return
        payload = json.dumps(event.raw)
        self._file.write(payload + "\n")
        if self.flush:
            self._file.flush()

    def close(self):
        if self._file:
            self._file.close()
            self._file = None


class UnixSocketSink:
    """Broadcasts matched JSON events over a Unix domain socket server."""

    def __init__(self, socket_path: str):
        self.socket_path = socket_path
        self._server: Optional[asyncio.AbstractServer] = None
        self._clients: List[asyncio.StreamWriter] = []

    async def start(self):
        if os.path.exists(self.socket_path):
            try:
                os.unlink(self.socket_path)
            except OSError:
                pass

        self._server = await asyncio.start_unix_server(
            self._handle_client,
            path=self.socket_path,
        )

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self._clients.append(writer)
        try:
            # keep client alive until it disconnects
            while not reader.at_eof():
                data = await reader.read(1024)
                if not data:
                    break
        except (ConnectionResetError, asyncio.CancelledError):
            pass
        finally:
            # print(f"DEBUG: client {writer} disconnected")
            if writer in self._clients:
                self._clients.remove(writer)
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    def write_event(self, event: MevEvent):
        if not self._clients:
            return

        raw_data = json.dumps(event.raw).encode("utf-8") + b"\n"
        dead_writers = []

        for writer in self._clients:
            try:
                writer.write(raw_data)
            except (BrokenPipeError, ConnectionResetError):
                dead_writers.append(writer)

        # Prune disconnected clients immediately rather than waiting for next cycle
        for dead in dead_writers:
            if dead in self._clients:
                self._clients.remove(dead)
                try:
                    dead.close()
                except Exception:
                    pass

    async def close(self):
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

        for writer in list(self._clients):
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
        self._clients.clear()

        if os.path.exists(self.socket_path):
            try:
                os.unlink(self.socket_path)
            except OSError:
                pass
