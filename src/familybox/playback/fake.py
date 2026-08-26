"""In-memory playback engine for development without mpv or audio hardware."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class FakePlaybackSnapshot:
    started: bool
    closed: bool
    tracks: tuple[str, ...]
    track_index: int
    current_source: str | None
    position_seconds: float
    duration_seconds: float | None
    paused: bool
    volume: float
    completed: bool


class FakePlaybackEngine:
    """Thread-safe mpv substitute with monotonic playback time advancement."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
        track_durations: Mapping[str, float] | None = None,
        initial_volume: float = 50.0,
    ) -> None:
        self._clock = clock
        self._durations = {
            str(source): max(0.0, float(duration))
            for source, duration in (track_durations or {}).items()
        }
        self._lock = threading.RLock()
        self._started = False
        self._closed = False
        self._tracks: tuple[str, ...] = ()
        self._track_index = -1
        self._position = 0.0
        self._last_clock = self._clock()
        self._paused = True
        self._volume = min(100.0, max(0.0, float(initial_volume)))
        self._completed = False

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._started and not self._closed

    @property
    def current_source(self) -> str | None:
        with self._lock:
            self._sync_position()
            return self._source()

    def start(self) -> None:
        with self._lock:
            if self._closed:
                raise RuntimeError("fake playback engine is closed")
            self._started = True
            self._last_clock = self._clock()

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
        with self._lock:
            self._ensure_ready()
            self._tracks = tuple(str(track) for track in tracks)
            self._track_index = start_index
            self._position = max(0.0, float(position_seconds))
            duration = self._duration()
            if duration is not None:
                self._position = min(self._position, duration)
            self._paused = False
            self._completed = False
            self._last_clock = self._clock()

    def pause(self) -> None:
        with self._lock:
            self._ensure_ready()
            self._sync_position()
            self._paused = True

    def resume(self) -> None:
        with self._lock:
            self._ensure_ready()
            self._sync_position()
            if self._tracks and not self._completed:
                self._paused = False
                self._last_clock = self._clock()

    def next(self) -> None:
        with self._lock:
            self._ensure_ready()
            self._sync_position()
            if self._track_index + 1 < len(self._tracks):
                self._track_index += 1
                self._position = 0.0
                self._completed = False
                self._last_clock = self._clock()

    def previous(self) -> None:
        with self._lock:
            self._ensure_ready()
            self._sync_position()
            if self._track_index > 0:
                self._track_index -= 1
            self._position = 0.0
            self._completed = False
            self._last_clock = self._clock()

    def seek(self, position_seconds: float) -> None:
        with self._lock:
            self._ensure_ready()
            self._sync_position()
            self._position = max(0.0, float(position_seconds))
            duration = self._duration()
            if duration is not None:
                self._position = min(self._position, duration)
            self._completed = False
            self._last_clock = self._clock()

    def set_volume(self, value: float) -> None:
        with self._lock:
            self._ensure_ready()
            self._volume = min(100.0, max(0.0, float(value)))

    def get_property(self, name: str) -> Any:
        with self._lock:
            self._ensure_ready()
            self._sync_position()
            source = self._source()
            values: dict[str, Any] = {
                "playlist-pos": self._track_index,
                "playlist-count": len(self._tracks),
                "time-pos": self._position if self._tracks else None,
                "duration": self._duration(),
                "pause": self._paused,
                "volume": self._volume,
                "eof-reached": self._completed,
                "idle-active": not self._tracks or self._completed,
                "path": source,
                "media-title": Path(source).name if source else None,
            }
            return values.get(name)

    def set_property(self, name: str, value: Any) -> None:
        if name == "pause":
            self.pause() if bool(value) else self.resume()
        elif name == "volume":
            self.set_volume(float(value))
        elif name == "playlist-pos":
            with self._lock:
                self._ensure_ready()
                index = int(value)
                if not 0 <= index < len(self._tracks):
                    raise ValueError("playlist position is out of range")
                self._track_index = index
                self._position = 0.0
                self._completed = False
                self._last_clock = self._clock()
        else:
            raise ValueError(f"unsupported fake playback property: {name}")

    def stop(self) -> None:
        with self._lock:
            self._ensure_ready()
            self._sync_position()
            self._tracks = ()
            self._track_index = -1
            self._position = 0.0
            self._paused = True
            self._completed = False

    def snapshot(self) -> FakePlaybackSnapshot:
        with self._lock:
            self._sync_position()
            return FakePlaybackSnapshot(
                started=self._started,
                closed=self._closed,
                tracks=self._tracks,
                track_index=self._track_index,
                current_source=self._source(),
                position_seconds=self._position,
                duration_seconds=self._duration(),
                paused=self._paused,
                volume=self._volume,
                completed=self._completed,
            )

    def simulate_crash(self) -> None:
        """Drop process-local state so manager recovery can be tested."""

        with self._lock:
            self._sync_position()
            self._started = False
            self._tracks = ()
            self._track_index = -1
            self._position = 0.0
            self._paused = True
            self._completed = False

    def _source(self) -> str | None:
        if 0 <= self._track_index < len(self._tracks):
            return self._tracks[self._track_index]
        return None

    def _duration(self) -> float | None:
        source = self._source()
        return self._durations.get(source) if source is not None else None

    def _sync_position(self) -> None:
        now = self._clock()
        if not self._started or self._paused or not self._tracks or self._completed:
            self._last_clock = now
            return
        self._position += max(0.0, now - self._last_clock)
        self._last_clock = now

        duration = self._duration()
        while duration is not None and self._position >= duration:
            overflow = self._position - duration
            if self._track_index + 1 >= len(self._tracks):
                self._position = duration
                self._completed = True
                self._paused = True
                return
            self._track_index += 1
            self._position = overflow
            duration = self._duration()

    def _ensure_ready(self) -> None:
        if self._closed:
            raise RuntimeError("fake playback engine is closed")
        if not self._started:
            raise RuntimeError("fake playback engine has not been started")

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            if self._started:
                self._sync_position()
            self._paused = True
            self._closed = True
