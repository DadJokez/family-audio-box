"""Provider-neutral playback orchestration and durable resume state."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from familybox.content.base import PlayableContent
from familybox.domain.models import PlaybackState

logger = logging.getLogger(__name__)


class PlaybackEngine(Protocol):
    @property
    def is_running(self) -> bool: ...

    def start(self) -> None: ...

    def load_playlist(
        self,
        tracks: list[str],
        *,
        start_index: int = 0,
        position_seconds: float = 0.0,
    ) -> None: ...

    def pause(self) -> None: ...

    def resume(self) -> None: ...

    def next(self) -> None: ...

    def previous(self) -> None: ...

    def seek(self, position_seconds: float) -> None: ...

    def set_volume(self, value: float) -> None: ...

    def get_property(self, name: str) -> Any: ...

    def stop(self) -> None: ...

    def close(self) -> None: ...


class PlaybackStateStore(Protocol):
    def get_playback_state(self, device_id: str, content_id: str) -> PlaybackState | None: ...

    def save_playback_state(self, state: PlaybackState) -> PlaybackState: ...


@dataclass(frozen=True, slots=True)
class PlaybackStatus:
    content_id: str | None
    title: str | None
    track_title: str | None
    source: str | None
    track_index: int
    track_count: int
    position_seconds: float
    duration_seconds: float | None
    paused: bool
    volume: int
    completed: bool


class PlaybackManager:
    """Keep mpv alive and persist per-device progress at write-safe intervals."""

    def __init__(
        self,
        engine: PlaybackEngine,
        state_store: PlaybackStateStore,
        *,
        device_id: str,
        progress_interval_seconds: float = 60.0,
        initial_volume: int = 50,
    ) -> None:
        if not device_id:
            raise ValueError("device_id is required for device-specific progress")
        if progress_interval_seconds <= 0:
            raise ValueError("progress persistence interval must be positive")

        self.engine = engine
        self.state_store = state_store
        self.device_id = device_id
        self.progress_interval_seconds = progress_interval_seconds
        self._volume = self._clamp_volume(initial_volume)

        self._current: PlayableContent | None = None
        self._track_index = 0
        self._position_seconds = 0.0
        self._paused = True
        self._completed = False
        self._completion_persisted = False
        self._started = False
        self._closed = False
        self._lock = threading.RLock()
        self._stop_worker = threading.Event()
        self._worker: threading.Thread | None = None

    @property
    def current_content_id(self) -> str | None:
        with self._lock:
            return self._current.content.id if self._current else None

    def start(self) -> None:
        with self._lock:
            if self._closed:
                raise RuntimeError("playback manager is closed")
            if self._started:
                self._recover_engine_locked()
                return
            self.engine.start()
            self.engine.set_volume(self._volume)
            self._started = True
            self._worker = threading.Thread(
                target=self._persistence_worker,
                name="familybox-progress",
                daemon=True,
            )
            self._worker.start()

    def play(self, playable: PlayableContent) -> None:
        with self._lock:
            self.start()
            content_id = playable.content.id
            if self.current_content_id == content_id:
                self.resume()
                return
            self._persist_locked()

            state = self.state_store.get_playback_state(self.device_id, content_id)
            if state is None or state.completed or state.track_index >= len(playable.tracks):
                track_index, position_seconds = 0, 0.0
            else:
                track_index = state.track_index
                position_seconds = state.position_seconds

            ordered_tracks = sorted(playable.tracks, key=lambda track: track.track_index)
            self.engine.load_playlist(
                [track.source for track in ordered_tracks],
                start_index=track_index,
                position_seconds=position_seconds,
            )
            self.engine.resume()
            self._current = playable
            self._track_index = track_index
            self._position_seconds = position_seconds
            self._paused = False
            self._completed = False
            self._completion_persisted = False
            logger.info(
                "playback started",
                extra={
                    "content_id": content_id,
                    "track_index": track_index,
                    "position_seconds": position_seconds,
                },
            )

    def pause(self) -> None:
        with self._lock:
            if self._current is None:
                return
            self._paused = True
            if self.engine.is_running:
                self.engine.pause()
            self._persist_locked(recover_engine=False)

    def resume(self) -> None:
        with self._lock:
            if self._current is None:
                return
            self._recover_engine_locked()
            self._refresh_position_locked(persist_completion=False)
            if self._completed:
                self._restart_current_locked()
                self._persist_locked()
                return
            self.engine.resume()
            self._paused = False

    def toggle_pause(self) -> None:
        with self._lock:
            if self._current is None:
                return
            self._recover_engine_locked()
            self._refresh_position_locked(persist_completion=False)
            if self._paused:
                self.resume()
            else:
                self.pause()

    def next(self) -> None:
        with self._lock:
            if self._current is None:
                return
            self._recover_engine_locked()
            self._refresh_position_locked()
            if self._completed:
                # There is no chapter after the terminal playlist item.
                return
            if self._track_index == len(self._current.tracks) - 1:
                return
            self.engine.next()
            self._track_index = min(self._track_index + 1, len(self._current.tracks) - 1)
            self._position_seconds = 0.0
            self._completed = False
            self._completion_persisted = False
            self._persist_locked()

    def previous(self) -> None:
        with self._lock:
            if self._current is None:
                return
            self._recover_engine_locked()
            self._refresh_position_locked(persist_completion=False)
            if self._completed:
                # mpv has no active playlist entry once it returns to idle, so
                # playlist-prev cannot be relied on after natural completion.
                target_index = max(0, self._track_index - 1)
                ordered_tracks = sorted(
                    self._current.tracks,
                    key=lambda track: track.track_index,
                )
                self.engine.load_playlist(
                    [track.source for track in ordered_tracks],
                    start_index=target_index,
                    position_seconds=0.0,
                )
                self.engine.pause()
                self._track_index = target_index
                self._position_seconds = 0.0
                self._paused = True
                self._completed = False
                self._completion_persisted = False
                self._persist_locked()
                return
            if self._track_index == 0:
                self.engine.seek(0.0)
            else:
                self.engine.previous()
                self._track_index -= 1
            self._position_seconds = 0.0
            self._completed = False
            self._completion_persisted = False
            self._persist_locked()

    def seek(self, position_seconds: float) -> None:
        with self._lock:
            if self._current is None:
                return
            self._recover_engine_locked()
            self._refresh_position_locked(persist_completion=False)
            target_position = max(0.0, float(position_seconds))
            if self._completed:
                ordered_tracks = sorted(
                    self._current.tracks,
                    key=lambda track: track.track_index,
                )
                self.engine.load_playlist(
                    [track.source for track in ordered_tracks],
                    start_index=self._track_index,
                    position_seconds=target_position,
                )
                self.engine.pause()
                self._position_seconds = target_position
                self._paused = True
                self._completed = False
                self._completion_persisted = False
                self._persist_locked()
                return
            self._position_seconds = target_position
            self._completed = False
            self._completion_persisted = False
            self.engine.seek(self._position_seconds)

    def stop(self) -> None:
        """Persist and unload the current queue without shutting down mpv."""

        with self._lock:
            if not self._started:
                return
            if self._current is not None:
                self._paused = True
                if self.engine.is_running:
                    self.engine.pause()
                self._persist_locked(recover_engine=False)
            if self.engine.is_running:
                self.engine.stop()
            self._current = None
            self._track_index = 0
            self._position_seconds = 0.0
            self._paused = True
            self._completed = False
            self._completion_persisted = False

    def set_volume(self, value: int | float) -> int:
        with self._lock:
            self.start()
            self._volume = self._clamp_volume(value)
            self.engine.set_volume(self._volume)
            return self._volume

    def adjust_volume(self, delta: int | float) -> int:
        with self._lock:
            return self.set_volume(self._volume + delta)

    @staticmethod
    def _clamp_volume(value: int | float) -> int:
        return round(min(100.0, max(0.0, float(value))))

    def status(self) -> PlaybackStatus:
        with self._lock:
            if self._current is None:
                return PlaybackStatus(
                    content_id=None,
                    title=None,
                    track_title=None,
                    source=None,
                    track_index=0,
                    track_count=0,
                    position_seconds=0.0,
                    duration_seconds=None,
                    paused=True,
                    volume=self._volume,
                    completed=False,
                )
            self._recover_engine_locked()
            self._refresh_position_locked()
            duration = self._safe_property("duration", None)
            ordered_tracks = sorted(self._current.tracks, key=lambda track: track.track_index)
            current_track = ordered_tracks[self._track_index]
            return PlaybackStatus(
                content_id=self._current.content.id,
                title=self._current.content.title,
                track_title=current_track.title,
                source=current_track.source,
                track_index=self._track_index,
                track_count=len(self._current.tracks),
                position_seconds=self._position_seconds,
                duration_seconds=float(duration) if duration is not None else None,
                paused=self._paused,
                volume=self._volume,
                completed=self._completed,
            )

    def persist(self) -> PlaybackState | None:
        with self._lock:
            return self._persist_locked()

    def _persist_locked(self, *, recover_engine: bool = True) -> PlaybackState | None:
        if self._current is None:
            return None
        if recover_engine:
            self._recover_engine_locked()
        if self.engine.is_running:
            self._refresh_position_locked(persist_completion=False)
        return self._save_cached_state_locked()

    def _save_cached_state_locked(self) -> PlaybackState:
        assert self._current is not None
        state = PlaybackState(
            device_id=self.device_id,
            content_id=self._current.content.id,
            track_index=self._track_index,
            position_seconds=self._position_seconds,
            completed=self._completed,
            updated_at=datetime.now(UTC),
        )
        self.state_store.save_playback_state(state)
        self._completion_persisted = state.completed
        logger.debug(
            "playback progress persisted",
            extra={
                "device_id": self.device_id,
                "content_id": state.content_id,
                "track_index": state.track_index,
                "position_seconds": state.position_seconds,
            },
        )
        return state

    def _refresh_position_locked(self, *, persist_completion: bool = True) -> None:
        if self._current is None:
            return
        playlist_position = self._safe_property("playlist-pos", None)
        has_playlist_position = (
            isinstance(playlist_position, (int, float)) and playlist_position >= 0
        )
        if has_playlist_position:
            self._track_index = min(
                int(playlist_position),
                len(self._current.tracks) - 1,
            )
        position = self._safe_property("time-pos", self._position_seconds)
        if isinstance(position, (int, float)) and position >= 0:
            self._position_seconds = float(position)
        paused = bool(self._safe_property("pause", self._paused))
        eof = bool(self._safe_property("eof-reached", self._completed))
        idle = bool(self._safe_property("idle-active", self._completed))
        if idle and not has_playlist_position:
            # Once mpv returns to idle it may expose playlist-pos as nil/-1.
            # The manager still owns the original queue, so its terminal item
            # is the only meaningful persisted index.
            self._track_index = len(self._current.tracks) - 1
        at_final_track = self._track_index == len(self._current.tracks) - 1
        if self._completed or (at_final_track and (eof or idle)):
            # mpv clears ``eof-reached`` after returning to idle when
            # ``--keep-open=no``.  Treat final-track idle as completion and
            # latch it until an explicit restart so progress writes stop.
            self._completed = True
            self._paused = True
        else:
            self._paused = paused
        if self._completed and persist_completion and not self._completion_persisted:
            try:
                self._save_cached_state_locked()
            except Exception:
                # Status reads must not fail just because the completion
                # checkpoint could not be written. The worker will retry.
                logger.exception("completed playback checkpoint failed")

    def _recover_engine_locked(self) -> None:
        """Restart a dead engine and restore the in-memory queue exactly once."""

        if not self._started or self.engine.is_running:
            return
        logger.warning(
            "playback engine stopped unexpectedly; restoring queue",
            extra={"content_id": self.current_content_id},
        )
        self.engine.start()
        self.engine.set_volume(self._volume)
        if self._current is None:
            return

        ordered_tracks = sorted(self._current.tracks, key=lambda track: track.track_index)
        self.engine.load_playlist(
            [track.source for track in ordered_tracks],
            start_index=self._track_index,
            position_seconds=self._position_seconds,
        )
        if self._paused:
            self.engine.pause()
        else:
            self.engine.resume()

    def _restart_current_locked(self) -> None:
        """Restart completed content from its first track in the same runtime."""

        if self._current is None:
            return
        ordered_tracks = sorted(self._current.tracks, key=lambda track: track.track_index)
        self.engine.load_playlist(
            [track.source for track in ordered_tracks],
            start_index=0,
            position_seconds=0.0,
        )
        self.engine.resume()
        self._track_index = 0
        self._position_seconds = 0.0
        self._paused = False
        self._completed = False
        self._completion_persisted = False

    def _safe_property(self, name: str, default: Any) -> Any:
        if not self._started:
            return default
        try:
            value = self.engine.get_property(name)
        except Exception:
            logger.warning(
                "unable to read mpv property",
                extra={"property": name},
                exc_info=True,
            )
            return default
        return default if value is None else value

    def _persistence_worker(self) -> None:
        while not self._stop_worker.wait(self.progress_interval_seconds):
            try:
                with self._lock:
                    completion_needs_save = self._completed and not self._completion_persisted
                    if self._current is not None and (not self._paused or completion_needs_save):
                        self._persist_locked()
            except Exception:
                # A transient persistence failure must never kill physical
                # playback.  The next interval/pause/shutdown will retry.
                logger.exception("periodic playback progress persistence failed")

    def shutdown(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._stop_worker.set()
            # A dead player has no newer observable position. Save the latest
            # cached state without restarting mpv during graceful shutdown.
            self._persist_locked(recover_engine=False)
            self._closed = True
        worker = self._worker
        if worker is not None and worker is not threading.current_thread():
            worker.join(timeout=min(2.0, self.progress_interval_seconds + 0.1))
        self.engine.close()

    close = shutdown
