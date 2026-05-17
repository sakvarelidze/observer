"""Utilities for managing a local cloudflared tunnel."""
from __future__ import annotations

import asyncio
import shutil
from asyncio.subprocess import Process
from typing import Optional


class CloudflaredManager:
    """Manage a background cloudflared process."""

    def __init__(self) -> None:
        self.process: Process | None = None
        self.token: Optional[str] = None
        # Lazy-init the Lock — asyncio.Lock() in Python 3.9 calls
        # events.get_event_loop() at construction, which raises if no
        # loop exists yet. CloudflaredManager() is constructed
        # synchronously inside create_app() (before the FastAPI lifespan
        # starts), so deferring lock creation to first async use lets
        # create_app() be called from any context.
        self._lock: asyncio.Lock | None = None
        self.error_message: str = ""
        self.status_message: str = ""
        self._watch_task: asyncio.Task[None] | None = None

    @property
    def lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def set_token(self, token: Optional[str]) -> None:
        """Persist the tunnel token in memory."""

        self.token = token or None

    def is_installed(self) -> bool:
        """Return True if the cloudflared binary exists."""

        return shutil.which("cloudflared") is not None

    def is_running(self) -> bool:
        """Return True if a managed process is currently active."""

        proc = self.process
        if proc and proc.returncode is not None:
            self.process = None
        return self.process is not None

    def status(self) -> dict:
        """Return the current status payload for the UI."""

        return {
            "installed": self.is_installed(),
            "running": self.is_running(),
            "errorMessage": self.error_message,
            "message": self.status_message,
            "token": self.token or "",
        }

    async def start(self, token: Optional[str] = None) -> tuple[bool, str]:
        """Start cloudflared using *token*.

        Returns a tuple ``(ok, message)`` describing the result.
        """

        async with self.lock:
            if token:
                self.set_token(token)

            if not self.token:
                return False, "missingToken"

            if self.is_running():
                return True, "alreadyRunning"

            if not self.is_installed():
                self.error_message = "cloudflared executable not found"
                return False, "notInstalled"

            self.error_message = ""
            self.status_message = "Starting cloudflared"

            try:
                process = await self._spawn_process(self.token)
            except FileNotFoundError:
                self.error_message = "cloudflared executable not found"
                return False, "notInstalled"
            except Exception as exc:  # pragma: no cover - defensive
                self.error_message = str(exc)
                return False, "startFailed"

            self.process = process
            self._watch_task = asyncio.create_task(self._watch_process(process))
            return True, "started"

    async def stop(self) -> tuple[bool, str]:
        """Stop the managed cloudflared process if running."""

        async with self.lock:
            if not self.is_running():
                return False, "notRunning"

            assert self.process is not None
            proc = self.process
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=10)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()

            self.status_message = "Stopped cloudflared"
            self.process = None
            return True, "stopped"

    async def _watch_process(self, process: Process) -> None:
        """Capture stdout/stderr from *process* and update status."""

        stdout = b""
        stderr = b""
        try:
            stdout, stderr = await process.communicate()
        finally:
            if process.returncode and process.returncode != 0:
                message = stderr.decode().strip() or stdout.decode().strip()
                if not message:
                    message = f"cloudflared exited with code {process.returncode}"
                self.error_message = message
            elif process.returncode == 0:
                self.error_message = ""
            self.status_message = "Stopped cloudflared"
            if self.process is process:
                self.process = None

    async def _spawn_process(self, token: str | None) -> Process:
        if not token:
            raise ValueError("cloudflared token is required")
        return await asyncio.create_subprocess_exec(
            "cloudflared",
            "tunnel",
            "--no-autoupdate",
            "run",
            "--token",
            token,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
