"""Persistent mpv process controlled through its JSON IPC protocol."""

from __future__ import annotations

import json
import logging
import socket
import stat
import subprocess
import threading
import time
from collections.abc import Sequence
from contextlib import suppress
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class MpvError(RuntimeError):
    """Base error for mpv process and IPC failures."""


class MpvUnavailableError(MpvError):
    """Raised when mpv cannot be started or reached."""


class MpvCommandError(MpvError):
    """Raised when mpv rejects a JSON IPC command."""


class MpvClient:
    """Own one idle mpv process and reuse one Unix-domain IPC connection."""

    def __init__(
        self,
        *,
        executable: str = "mpv",
        socket_path: Path | str | None = None,
        audio_device: str | None = None,
        extra_args: Sequence[str] = (),
        start_timeout_seconds: float = 5.0,
        command_timeout_seconds: float = 3.0,
        manage_process: bool = True,
    ) -> None:
        generated_name = f"familybox-mpv-{uuid4().hex}.sock"
        # Darwin and Linux cap AF_UNIX paths (commonly 104/108 bytes).  `/tmp`
        # keeps the generated name valid even when the user's temp dir is long.
        self.socket_path = Path(socket_path or Path("/tmp") / generated_name)
        self.executable = executable
        self.audio_device = audio_device
        self.extra_args = tuple(extra_args)
        self.start_timeout_seconds = start_timeout_seconds
        self.command_timeout_seconds = command_timeout_seconds
        self.manage_process = manage_process

        self._process: subprocess.Popen[bytes] | None = None
        self._socket: socket.socket | None = None
        self._receive_buffer = b""
        self._request_id = 0
        self._lock = threading.RLock()
        self._created_socket = False

    @property
    def process(self) -> subprocess.Popen[bytes] | None:
        return self._process

    @property
    def is_running(self) -> bool:
        if self.manage_process:
            return self._process is not None and self._process.poll() is None
        return self._socket is not None

    def _process_args(self) -> list[str]:
        args = [
            self.executable,
            "--idle=yes",
            "--no-terminal",
            "--force-window=no",
            "--audio-display=no",
            "--keep-open=no",
            "--save-position-on-quit=no",
            f"--input-ipc-server={self.socket_path}",
        ]
        if self.audio_device:
            args.append(f"--audio-device={self.audio_device}")
        args.extend(self.extra_args)
        return args

    def start(self) -> None:
        with self._lock:
            if self.manage_process and self._process is not None:
                if self._process.poll() is None:
                    self._connect()
                    return
                self._process = None

            if not self.manage_process:
                self._connect()
                return

            self._prepare_socket_path()

            try:
                self._process = subprocess.Popen(
                    self._process_args(),
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
            except OSError as exc:
                raise MpvUnavailableError(f"unable to start {self.executable!r}: {exc}") from exc

            deadline = time.monotonic() + self.start_timeout_seconds
            while time.monotonic() < deadline:
                if self._process.poll() is not None:
                    return_code = self._process.returncode
                    self._process = None
                    self._cleanup_owned_socket()
                    raise MpvUnavailableError(
                        f"mpv exited before creating its IPC socket (status {return_code})"
                    )
                if self.socket_path.exists():
                    self._created_socket = True
                    try:
                        self._connect()
                    except MpvUnavailableError:
                        # The socket pathname can become visible just before
                        # mpv begins accepting connections.
                        time.sleep(0.02)
                        continue
                    logger.info("mpv started", extra={"socket_path": str(self.socket_path)})
                    return
                time.sleep(0.02)

            self._terminate_process()
            self._cleanup_owned_socket()
            raise MpvUnavailableError(
                f"mpv IPC socket did not appear within {self.start_timeout_seconds:g}s"
            )

    def _prepare_socket_path(self) -> None:
        """Remove only a verified stale socket left by an unclean shutdown."""

        try:
            existing = self.socket_path.lstat()
        except FileNotFoundError:
            return
        if self.socket_path.is_symlink() or not stat.S_ISSOCK(existing.st_mode):
            raise MpvUnavailableError(
                f"refusing to replace non-socket mpv IPC path: {self.socket_path}"
            )

        probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        probe.settimeout(0.2)
        try:
            probe.connect(str(self.socket_path))
        except OSError:
            try:
                current = self.socket_path.lstat()
            except FileNotFoundError:
                return
            if (current.st_dev, current.st_ino) != (existing.st_dev, existing.st_ino):
                raise MpvUnavailableError(
                    f"mpv IPC socket changed while checking it: {self.socket_path}"
                ) from None
            self.socket_path.unlink()
            logger.info(
                "removed stale mpv IPC socket", extra={"socket_path": str(self.socket_path)}
            )
        else:
            raise MpvUnavailableError(f"an mpv IPC server is already active: {self.socket_path}")
        finally:
            probe.close()

    def connect(self) -> None:
        """Connect to an already-running mpv (useful for diagnostics/tests)."""

        with self._lock:
            self._connect()

    def _connect(self) -> None:
        if self._socket is not None:
            return
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        connection.settimeout(self.command_timeout_seconds)
        try:
            connection.connect(str(self.socket_path))
        except OSError as exc:
            connection.close()
            raise MpvUnavailableError(
                f"unable to connect to mpv IPC socket {self.socket_path}: {exc}"
            ) from exc
        self._socket = connection
        self._receive_buffer = b""

    def request(self, command: Sequence[Any]) -> Any:
        """Send one JSON IPC command and return its ``data`` value."""

        with self._lock:
            if self._socket is None:
                self.start()
            assert self._socket is not None

            self._request_id += 1
            request_id = self._request_id
            encoded_command = [
                str(value) if isinstance(value, Path) else value for value in command
            ]
            payload = (
                json.dumps(
                    {"command": encoded_command, "request_id": request_id},
                    separators=(",", ":"),
                ).encode("utf-8")
                + b"\n"
            )
            try:
                self._socket.sendall(payload)
                while True:
                    response = self._receive_message()
                    if response.get("request_id") != request_id:
                        # Property-change and playback events share the IPC stream.
                        continue
                    error = response.get("error", "success")
                    if error != "success":
                        raise MpvCommandError(f"mpv command {encoded_command[0]!r} failed: {error}")
                    return response.get("data")
            except (OSError, TimeoutError, json.JSONDecodeError) as exc:
                self._disconnect()
                raise MpvUnavailableError(f"mpv IPC request failed: {exc}") from exc

    def _receive_message(self) -> dict[str, Any]:
        assert self._socket is not None
        while b"\n" not in self._receive_buffer:
            chunk = self._socket.recv(65536)
            if not chunk:
                raise ConnectionError("mpv closed the IPC connection")
            self._receive_buffer += chunk
            if len(self._receive_buffer) > 4 * 1024 * 1024:
                raise MpvError("mpv IPC response exceeded 4 MiB")
        line, self._receive_buffer = self._receive_buffer.split(b"\n", 1)
        message = json.loads(line)
        if not isinstance(message, dict):
            raise MpvError("mpv returned a non-object IPC response")
        return message

    def command(self, name: str, *arguments: Any) -> Any:
        return self.request((name, *arguments))

    def get_property(self, name: str) -> Any:
        return self.command("get_property", name)

    def set_property(self, name: str, value: Any) -> None:
        self.command("set_property", name, value)

    def load_playlist(
        self,
        tracks: Sequence[str | Path],
        *,
        start_index: int = 0,
        position_seconds: float = 0.0,
    ) -> None:
        if not tracks:
            raise ValueError("cannot load an empty playlist")
        if not 0 <= start_index < len(tracks):
            raise ValueError("playlist start index is out of range")

        self.command("stop")
        self.command("playlist-clear")
        self.command("loadfile", str(tracks[0]), "replace")
        for track in tracks[1:]:
            self.command("loadfile", str(track), "append")
        if start_index:
            self.set_property("playlist-pos", start_index)
        if position_seconds > 0:
            self.command("seek", float(position_seconds), "absolute+exact")

    def pause(self) -> None:
        self.set_property("pause", True)

    def resume(self) -> None:
        self.set_property("pause", False)

    def next(self) -> None:
        self.command("playlist-next", "weak")

    def previous(self) -> None:
        self.command("playlist-prev", "weak")

    def seek(self, position_seconds: float) -> None:
        self.command("seek", max(0.0, float(position_seconds)), "absolute+exact")

    def set_volume(self, value: float) -> None:
        self.set_property("volume", min(100.0, max(0.0, float(value))))

    def stop(self) -> None:
        self.command("stop")

    def _disconnect(self) -> None:
        connection, self._socket = self._socket, None
        self._receive_buffer = b""
        if connection is not None:
            with suppress(OSError):
                connection.close()

    def _terminate_process(self) -> None:
        process, self._process = self._process, None
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)

    def _cleanup_owned_socket(self) -> None:
        if not self._created_socket:
            return
        try:
            self.socket_path.unlink(missing_ok=True)
        except OSError:
            logger.warning(
                "unable to remove stale mpv socket",
                extra={"socket_path": str(self.socket_path)},
                exc_info=True,
            )
        self._created_socket = False

    def close(self) -> None:
        with self._lock:
            if self.manage_process and self._socket is not None:
                with suppress(MpvError):
                    self.command("quit")
            self._disconnect()
            if self.manage_process:
                process = self._process
                if process is not None:
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        self._terminate_process()
                    else:
                        self._process = None
            self._cleanup_owned_socket()

    def __enter__(self) -> MpvClient:
        self.start()
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()
