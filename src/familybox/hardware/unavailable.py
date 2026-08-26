"""Inert adapters used when a configured peripheral cannot be initialized.

These are deliberately distinct from the development fakes: they keep the
process and diagnostic UI alive without pretending failed hardware is present.
"""

from __future__ import annotations

from threading import Event

from familybox.hardware.interfaces import (
    AudioOutput,
    AudioOutputStatus,
    ButtonAction,
    ButtonController,
    NfcReader,
    PowerMonitor,
    PowerStatus,
    VolumeController,
    VolumeEvent,
)


class UnavailableNfcReader(NfcReader):
    def __init__(self, error: str) -> None:
        self.error = error
        self._closed = Event()

    def read_uid(self, timeout_seconds: float = 0.2) -> None:
        self._closed.wait(max(0.0, timeout_seconds))
        return None

    def close(self) -> None:
        self._closed.set()


class UnavailableButtonController(ButtonController):
    def __init__(self, error: str) -> None:
        self.error = error
        self._closed = Event()

    def read_action(self, timeout_seconds: float = 0.2) -> ButtonAction | None:
        self._closed.wait(max(0.0, timeout_seconds))
        return None

    def close(self) -> None:
        self._closed.set()


class UnavailableVolumeController(VolumeController):
    def __init__(self, error: str) -> None:
        self.error = error
        self._closed = Event()

    def read_event(self, timeout_seconds: float = 0.2) -> VolumeEvent | None:
        self._closed.wait(max(0.0, timeout_seconds))
        return None

    def close(self) -> None:
        self._closed.set()


class UnavailablePowerMonitor(PowerMonitor):
    def __init__(self, error: str) -> None:
        self.error = error

    def status(self) -> PowerStatus:
        raise RuntimeError(self.error)

    def close(self) -> None:
        pass


class UnavailableAudioOutput(AudioOutput):
    def __init__(self, error: str) -> None:
        self.error = error

    def prepare(self) -> None:
        raise RuntimeError(self.error)

    def status(self) -> AudioOutputStatus:
        return AudioOutputStatus(available=False, device="unavailable", detail=self.error)

    def close(self) -> None:
        pass
