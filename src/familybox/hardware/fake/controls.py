"""Queue-backed fake physical controls."""

from __future__ import annotations

from queue import Empty, Queue

from familybox.hardware.interfaces import (
    ButtonAction,
    ButtonController,
    VolumeController,
    VolumeEvent,
)


class FakeButtonController(ButtonController):
    def __init__(self) -> None:
        self._events: Queue[ButtonAction] = Queue()
        self._closed = False

    def press(self, action: ButtonAction | str) -> None:
        self._ensure_open()
        self._events.put(ButtonAction(action))

    def read_action(self, timeout_seconds: float = 0.2) -> ButtonAction | None:
        self._ensure_open()
        try:
            return self._events.get(timeout=max(timeout_seconds, 0))
        except Empty:
            return None

    def close(self) -> None:
        self._closed = True

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("fake button controller is closed")


class FakeVolumeController(VolumeController):
    def __init__(self) -> None:
        self._events: Queue[VolumeEvent] = Queue()
        self._closed = False

    def rotate(self, delta: int) -> None:
        self._ensure_open()
        if delta == 0:
            return
        step = 1 if delta > 0 else -1
        for _ in range(abs(delta)):
            self._events.put(VolumeEvent(delta=step))

    def press(self) -> None:
        self._ensure_open()
        self._events.put(VolumeEvent(pressed=True))

    def read_event(self, timeout_seconds: float = 0.2) -> VolumeEvent | None:
        self._ensure_open()
        try:
            return self._events.get(timeout=max(timeout_seconds, 0))
        except Empty:
            return None

    def close(self) -> None:
        self._closed = True

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("fake volume controller is closed")
