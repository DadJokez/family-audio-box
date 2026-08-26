"""GPIO controls using gpiozero with internal pull-ups."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from queue import Empty, Full, Queue
from typing import Any

from familybox.hardware.interfaces import (
    ButtonAction,
    ButtonController,
    VolumeController,
    VolumeEvent,
)

BUTTON_PINS: dict[ButtonAction, int] = {
    ButtonAction.PREVIOUS: 5,
    ButtonAction.PLAY_PAUSE: 6,
    ButtonAction.NEXT: 13,
}
ENCODER_A_PIN = 23
ENCODER_B_PIN = 24
ENCODER_PUSH_PIN = 25


def _queue_latest(queue: Queue[Any], event: Any) -> None:
    """Never block a GPIO callback if a consumer falls behind."""

    try:
        queue.put_nowait(event)
        return
    except Full:
        pass
    with suppress(Empty):
        queue.get_nowait()
    with suppress(Full):
        queue.put_nowait(event)


class GpioButtonController(ButtonController):
    def __init__(
        self,
        *,
        button_factory: Callable[..., Any] | None = None,
        bounce_time: float = 0.05,
    ) -> None:
        if button_factory is None:
            try:
                from gpiozero import Button  # type: ignore[import-not-found]
            except ImportError as exc:  # pragma: no cover - exercised on Pi
                raise RuntimeError(
                    "GPIO controls require the FamilyBox 'pi' optional dependencies"
                ) from exc
            button_factory = Button

        self._events: Queue[ButtonAction] = Queue(maxsize=64)
        self._buttons: list[Any] = []
        self._closed = False
        for action, pin in BUTTON_PINS.items():
            button = button_factory(pin, pull_up=True, bounce_time=bounce_time)
            button.when_pressed = self._callback(action)
            self._buttons.append(button)

    def _callback(self, action: ButtonAction) -> Callable[..., None]:
        def emit(*_args: Any) -> None:
            if not self._closed:
                _queue_latest(self._events, action)

        return emit

    def read_action(self, timeout_seconds: float = 0.2) -> ButtonAction | None:
        if self._closed:
            raise RuntimeError("GPIO button controller is closed")
        try:
            return self._events.get(timeout=max(timeout_seconds, 0))
        except Empty:
            return None

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for button in self._buttons:
            button.close()
        self._buttons.clear()


class GpioVolumeController(VolumeController):
    def __init__(
        self,
        *,
        encoder_factory: Callable[..., Any] | None = None,
        button_factory: Callable[..., Any] | None = None,
        bounce_time: float = 0.05,
    ) -> None:
        if encoder_factory is None or button_factory is None:
            try:
                from gpiozero import Button, RotaryEncoder
            except ImportError as exc:  # pragma: no cover - exercised on Pi
                raise RuntimeError(
                    "GPIO controls require the FamilyBox 'pi' optional dependencies"
                ) from exc
            encoder_factory = encoder_factory or RotaryEncoder
            button_factory = button_factory or Button

        self._events: Queue[VolumeEvent] = Queue(maxsize=64)
        self._closed = False
        self._encoder = encoder_factory(
            ENCODER_A_PIN,
            ENCODER_B_PIN,
            bounce_time=bounce_time,
            max_steps=0,
        )
        self._push = button_factory(
            ENCODER_PUSH_PIN,
            pull_up=True,
            bounce_time=bounce_time,
        )
        self._encoder.when_rotated_clockwise = self._emit(VolumeEvent(delta=1))
        self._encoder.when_rotated_counter_clockwise = self._emit(VolumeEvent(delta=-1))
        self._push.when_pressed = self._emit(VolumeEvent(pressed=True))

    def _emit(self, event: VolumeEvent) -> Callable[..., None]:
        def emit(*_args: Any) -> None:
            if not self._closed:
                _queue_latest(self._events, event)

        return emit

    def read_event(self, timeout_seconds: float = 0.2) -> VolumeEvent | None:
        if self._closed:
            raise RuntimeError("GPIO volume controller is closed")
        try:
            return self._events.get(timeout=max(timeout_seconds, 0))
        except Empty:
            return None

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._encoder.close()
        self._push.close()
