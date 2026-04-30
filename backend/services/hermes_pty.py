import asyncio
import os
import shutil
import signal
from typing import Callable, Awaitable

from ptyprocess import PtyProcess

DEFAULT_CMD = ["hermes", "chat"]
FALLBACK_CMD = ["zsh", "-il"]


def _default_cmd() -> list[str]:
    if shutil.which("hermes"):
        return DEFAULT_CMD
    return FALLBACK_CMD


class PtyBridge:
    def __init__(self, cmd: list[str] | None = None):
        self._cmd = cmd or _default_cmd()
        self._process: PtyProcess | None = None
        self._running = False
        self._on_output: Callable[[bytes], Awaitable[None]] | None = None
        self._read_task: asyncio.Task | None = None
        self._exit_code: int | None = None

    @property
    def exit_code(self) -> int | None:
        return self._exit_code

    async def start(self, on_output: Callable[[bytes], Awaitable[None]]):
        self._on_output = on_output
        loop = asyncio.get_event_loop()
        self._process = await loop.run_in_executor(
            None, lambda: PtyProcess.spawn(self._cmd)
        )
        self._running = True
        self._read_task = asyncio.create_task(self._read_loop())

    async def _read_loop(self):
        loop = asyncio.get_event_loop()
        while self._running and self._process is not None:
            try:
                data = await loop.run_in_executor(
                    None, lambda: self._process.read(4096)
                )
                if not data:
                    break
                if self._on_output:
                    await self._on_output(data)
            except asyncio.CancelledError:
                break
            except EOFError:
                break
            except Exception:
                break

        if self._process is not None:
            p = self._process
            try:
                await loop.run_in_executor(
                    None, lambda: p.close()
                )
            except Exception:
                pass
            self._exit_code = getattr(p, "exitstatus", None)
            if self._exit_code is None:
                self._exit_code = -1
        if self._on_output:
            await self._on_output(b"")

    def write(self, data: bytes):
        if self._process and self._running:
            self._process.write(data)

    def resize(self, rows: int, cols: int):
        if self._process:
            try:
                self._process.setwinsize(rows, cols)
            except Exception:
                pass

    async def stop(self):
        self._running = False
        if self._process:
            p = self._process
            self._process = None
            try:
                os.kill(p.pid, signal.SIGKILL)
            except Exception:
                pass
            await asyncio.sleep(0.1)
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None, lambda: p.close()
                )
            except Exception:
                pass
            self._exit_code = getattr(p, "exitstatus", None)
            if self._exit_code is None:
                self._exit_code = -1
        if self._read_task:
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass
