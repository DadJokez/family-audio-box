from __future__ import annotations

import threading
import time

import pytest

from familybox.content.base import PlayableContent, PlayableTrack
from familybox.domain.models import Content, PlaybackState
from familybox.playback.fake import FakePlaybackEngine
from familybox.playback.manager import PlaybackManager


class StateStore:
    def __init__(self) -> None:
        self.states: dict[tuple[str, str], PlaybackState] = {}
        self.saved: list[PlaybackState] = []
        self.completed_saved = threading.Event()

    def get_playback_state(self, device_id: str, content_id: str):
        return self.states.get((device_id, content_id))

    def save_playback_state(self, state: PlaybackState):
        self.states[(state.device_id, state.content_id)] = state
        self.saved.append(state)
        if state.completed:
            self.completed_saved.set()
        return state


class IdleClearingFakePlaybackEngine(FakePlaybackEngine):
    """Model mpv clearing EOF and its active playlist position in idle mode."""

    def get_property(self, name: str):
        value = super().get_property(name)
        if self.snapshot().completed:
            if name == "playlist-pos":
                return None
            if name == "eof-reached":
                return False
        return value

    def previous(self) -> None:
        if self.snapshot().completed:
            return
        super().previous()


def playable(content_id: str = "book") -> PlayableContent:
    content = Content(
        id=content_id,
        title="The Railway Children",
        provider="local",
        provider_reference=content_id,
    )
    return PlayableContent(
        content=content,
        tracks=(
            PlayableTrack("one", content_id, 0, "One", "/media/001.mp3", 100),
            PlayableTrack("two", content_id, 1, "Two", "/media/002.mp3", 100),
        ),
    )


def test_restores_and_persists_progress_for_only_this_device():
    now = [10.0]
    engine = FakePlaybackEngine(clock=lambda: now[0])
    store = StateStore()
    store.states[("box-a", "book")] = PlaybackState(
        device_id="box-a", content_id="book", track_index=1, position_seconds=12.5
    )
    store.states[("box-b", "book")] = PlaybackState(
        device_id="box-b", content_id="book", track_index=0, position_seconds=77
    )
    manager = PlaybackManager(engine, store, device_id="box-a", progress_interval_seconds=3600)

    manager.play(playable())
    assert engine.snapshot().track_index == 1
    assert engine.snapshot().position_seconds == 12.5

    now[0] += 7.5
    manager.pause()

    saved = store.states[("box-a", "book")]
    assert saved.track_index == 1
    assert saved.position_seconds == 20
    assert store.states[("box-b", "book")].position_seconds == 77
    manager.shutdown()


def test_navigation_volume_and_status_use_the_persistent_engine():
    engine = FakePlaybackEngine()
    store = StateStore()
    manager = PlaybackManager(engine, store, device_id="box-a", progress_interval_seconds=3600)
    manager.play(playable())

    manager.next()
    assert manager.status().track_index == 1
    assert manager.status().track_title == "Two"
    assert manager.status().source == "/media/002.mp3"
    manager.previous()
    assert manager.status().track_index == 0
    assert manager.adjust_volume(80) == 100
    assert manager.adjust_volume(-150) == 0
    assert engine.snapshot().volume == 0
    manager.shutdown()


def test_completed_content_restarts_from_the_beginning():
    engine = FakePlaybackEngine()
    store = StateStore()
    store.states[("box-a", "book")] = PlaybackState(
        device_id="box-a",
        content_id="book",
        track_index=1,
        position_seconds=99,
        completed=True,
    )
    manager = PlaybackManager(engine, store, device_id="box-a", progress_interval_seconds=3600)

    manager.play(playable())

    assert engine.snapshot().track_index == 0
    assert engine.snapshot().position_seconds == pytest.approx(0, abs=0.01)
    manager.shutdown()


def test_stop_persists_and_unloads_the_current_queue():
    engine = FakePlaybackEngine()
    store = StateStore()
    manager = PlaybackManager(engine, store, device_id="box-a", progress_interval_seconds=3600)
    manager.play(playable())

    manager.stop()

    assert manager.current_content_id is None
    assert manager.status().track_count == 0
    assert engine.snapshot().tracks == ()
    assert store.states[("box-a", "book")].position_seconds >= 0
    manager.shutdown()


def test_fake_engine_advances_with_clock_and_rolls_to_the_next_track():
    now = [0.0]
    engine = FakePlaybackEngine(
        clock=lambda: now[0],
        track_durations={"one.mp3": 5, "two.mp3": 10},
    )
    engine.start()
    engine.load_playlist(["one.mp3", "two.mp3"])

    now[0] = 7.0
    snapshot = engine.snapshot()

    assert snapshot.track_index == 1
    assert snapshot.current_source == "two.mp3"
    assert snapshot.position_seconds == 2
    engine.close()


def test_natural_final_eof_is_persisted_once_then_stops_periodic_writes():
    engine = FakePlaybackEngine(track_durations={"/media/001.mp3": 0.01, "/media/002.mp3": 0.01})
    store = StateStore()
    manager = PlaybackManager(
        engine,
        store,
        device_id="box-a",
        progress_interval_seconds=0.01,
    )

    manager.play(playable())

    assert store.completed_saved.wait(timeout=1)
    status = manager.status()
    assert status.completed is True
    assert status.paused is True
    assert sum(state.completed for state in store.saved) == 1
    save_count = len(store.saved)

    time.sleep(0.06)

    assert len(store.saved) == save_count
    manager.shutdown()


def test_final_idle_is_completion_when_mpv_has_cleared_eof_and_playlist_position():
    now = [0.0]
    engine = IdleClearingFakePlaybackEngine(
        clock=lambda: now[0],
        track_durations={"/media/001.mp3": 1, "/media/002.mp3": 1},
    )
    store = StateStore()
    manager = PlaybackManager(
        engine,
        store,
        device_id="box-a",
        progress_interval_seconds=3600,
    )
    manager.play(playable())

    now[0] = 3
    status = manager.status()

    assert status.track_index == 1
    assert status.completed is True
    assert status.paused is True
    assert store.states[("box-a", "book")].completed is True
    save_count = len(store.saved)
    assert manager.status().completed is True
    assert len(store.saved) == save_count
    manager.shutdown()


def test_seek_after_completion_reloads_the_idle_queue_at_requested_position():
    now = [0.0]
    engine = IdleClearingFakePlaybackEngine(
        clock=lambda: now[0],
        track_durations={"/media/001.mp3": 100, "/media/002.mp3": 100},
    )
    manager = PlaybackManager(
        engine,
        StateStore(),
        device_id="box-a",
        progress_interval_seconds=3600,
    )
    manager.play(playable())
    now[0] = 250
    assert manager.status().completed is True

    manager.seek(25)

    status = manager.status()
    assert status.track_index == 1
    assert status.position_seconds == 25
    assert status.completed is False
    assert status.paused is True
    manager.shutdown()


def test_previous_reloads_a_chapter_after_mpv_has_returned_to_idle():
    now = [0.0]
    engine = IdleClearingFakePlaybackEngine(
        clock=lambda: now[0],
        track_durations={"/media/001.mp3": 1, "/media/002.mp3": 1},
    )
    manager = PlaybackManager(
        engine,
        StateStore(),
        device_id="box-a",
        progress_interval_seconds=3600,
    )
    manager.play(playable())
    now[0] = 3
    assert manager.status().completed is True

    manager.next()
    terminal = manager.status()
    assert terminal.track_index == 1
    assert terminal.completed is True

    manager.previous()

    status = manager.status()
    assert status.track_index == 0
    assert status.position_seconds == 0
    assert status.completed is False
    assert status.paused is True
    manager.shutdown()


def test_completed_content_restarts_in_the_same_runtime_on_resume_or_represent():
    now = [0.0]
    engine = FakePlaybackEngine(
        clock=lambda: now[0],
        track_durations={"/media/001.mp3": 1, "/media/002.mp3": 1},
    )
    store = StateStore()
    manager = PlaybackManager(engine, store, device_id="box-a", progress_interval_seconds=3600)
    selected = playable()
    manager.play(selected)

    now[0] = 3
    assert manager.status().completed is True
    manager.resume()

    resumed = engine.snapshot()
    assert resumed.track_index == 0
    assert resumed.position_seconds == 0
    assert resumed.paused is False
    assert resumed.completed is False

    now[0] = 6
    assert manager.status().completed is True
    manager.play(selected)

    represented = engine.snapshot()
    assert represented.track_index == 0
    assert represented.position_seconds == 0
    assert represented.paused is False
    assert represented.completed is False
    manager.shutdown()


def test_dead_engine_reloads_current_queue_before_resume_and_navigation():
    now = [0.0]
    engine = FakePlaybackEngine(
        clock=lambda: now[0],
        track_durations={"/media/001.mp3": 100, "/media/002.mp3": 100},
    )
    store = StateStore()
    manager = PlaybackManager(engine, store, device_id="box-a", progress_interval_seconds=3600)
    manager.play(playable())

    now[0] = 12
    manager.pause()
    engine.simulate_crash()
    assert engine.is_running is False

    manager.resume()

    resumed = engine.snapshot()
    assert resumed.tracks == ("/media/001.mp3", "/media/002.mp3")
    assert resumed.track_index == 0
    assert resumed.position_seconds == 12
    assert resumed.paused is False

    now[0] = 17
    assert manager.status().position_seconds == 17
    engine.simulate_crash()

    manager.next()

    navigated = engine.snapshot()
    assert navigated.tracks == ("/media/001.mp3", "/media/002.mp3")
    assert navigated.track_index == 1
    assert navigated.position_seconds == 0
    assert navigated.paused is False
    manager.shutdown()


def test_shutdown_persists_cached_state_without_restarting_a_dead_engine():
    now = [0.0]
    engine = FakePlaybackEngine(
        clock=lambda: now[0],
        track_durations={"/media/001.mp3": 100, "/media/002.mp3": 100},
    )
    store = StateStore()
    manager = PlaybackManager(engine, store, device_id="box-a", progress_interval_seconds=3600)
    manager.play(playable())
    now[0] = 8
    assert manager.status().position_seconds == 8
    engine.simulate_crash()

    manager.shutdown()

    snapshot = engine.snapshot()
    assert snapshot.started is False
    assert snapshot.closed is True
    assert store.states[("box-a", "book")].position_seconds == 8


def test_pause_persists_cached_state_without_restarting_a_dead_engine():
    now = [0.0]
    engine = FakePlaybackEngine(
        clock=lambda: now[0],
        track_durations={"/media/001.mp3": 100, "/media/002.mp3": 100},
    )
    store = StateStore()
    manager = PlaybackManager(engine, store, device_id="box-a", progress_interval_seconds=3600)
    manager.play(playable())
    now[0] = 8
    assert manager.status().position_seconds == 8
    engine.simulate_crash()

    manager.pause()

    assert engine.is_running is False
    assert store.states[("box-a", "book")].position_seconds == 8
    manager.shutdown()
