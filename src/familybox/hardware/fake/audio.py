"""Fake audio output for non-Pi development."""

from familybox.hardware.interfaces import AudioOutput, AudioOutputStatus


class FakeAudioOutput(AudioOutput):
    def __init__(self, *, available: bool = True, device: str = "fake") -> None:
        self.available = available
        self.device = device
        self.prepared = False
        self.closed = False

    def prepare(self) -> None:
        if self.closed:
            raise RuntimeError("fake audio output is closed")
        if not self.available:
            raise RuntimeError("fake audio output is unavailable")
        self.prepared = True

    def status(self) -> AudioOutputStatus:
        return AudioOutputStatus(self.available and not self.closed, self.device)

    def close(self) -> None:
        self.closed = True
        self.prepared = False
