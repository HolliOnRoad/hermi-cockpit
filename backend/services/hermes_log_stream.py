import asyncio
import re
from datetime import datetime, timezone
from typing import Callable, Awaitable

LOG_PATTERN = re.compile(
    r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) (INFO|WARNING|ERROR|DEBUG) ([^:]+): (.+)$'
)

LEVEL_MAP = {"INFO": "info", "WARNING": "warning", "ERROR": "error", "DEBUG": "debug"}

TYPE_MAP = {"INFO": "log", "WARNING": "log", "ERROR": "error", "DEBUG": "log"}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


class HermesLogStream:
    def __init__(self):
        self._process: asyncio.subprocess.Process | None = None
        self._task: asyncio.Task | None = None
        self._broadcast: Callable[[dict], Awaitable[int]] | None = None
        self._running = False
        self._last_event: dict | None = None

    def set_broadcast(self, broadcast_fn: Callable[[dict], Awaitable[int]]):
        self._broadcast = broadcast_fn

    async def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run())

    async def _run(self):
        try:
            self._process = await asyncio.create_subprocess_exec(
                "hermes",
                "logs",
                "-f",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            assert self._process.stdout is not None

            async for line in self._process.stdout:
                if not self._running:
                    break
                decoded = line.decode("utf-8", errors="replace").rstrip("\n")
                await self._handle_line(decoded)

            await self._process.wait()
            self._process = None

        except FileNotFoundError:
            await self._broadcast({
                "type": "error",
                "level": "error",
                "source": "system",
                "message": "Hermes CLI nicht verfügbar",
                "timestamp": _now(),
            })
            self._process = None
        except Exception:
            self._process = None

    async def _handle_line(self, line: str):
        match = LOG_PATTERN.match(line)
        if match:
            ts, level, component, message = match.groups()
            event = {
                "type": TYPE_MAP.get(level, "log"),
                "level": LEVEL_MAP.get(level, "info"),
                "source": component,
                "message": message,
                "timestamp": ts,
            }
            self._last_event = event
            await self._broadcast(event) if self._broadcast else None
        elif self._last_event is not None:
            event = {
                "type": self._last_event.get("type", "log"),
                "level": self._last_event.get("level", "info"),
                "source": self._last_event.get("source", "hermes"),
                "message": line,
                "timestamp": self._last_event.get("timestamp", _now()),
                "meta": {"continuation": True},
            }
            await self._broadcast(event) if self._broadcast else None

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._process:
            try:
                self._process.terminate()
                await self._process.wait()
            except ProcessLookupError:
                pass


_log_stream = HermesLogStream()


def get_log_stream() -> HermesLogStream:
    return _log_stream
