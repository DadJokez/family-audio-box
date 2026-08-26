"""MAX98357A I2S output availability adapter."""

from __future__ import annotations

from pathlib import Path

from familybox.hardware.interfaces import AudioOutput, AudioOutputStatus


class Max98357aAudioOutput(AudioOutput):
    """Represent the system-configured ALSA device used by mpv.

    I2S pin mux and the device-tree overlay are configured during installation;
    application code does not manipulate GPIO18/19/21 directly.
    """

    def __init__(
        self,
        *,
        device: str = "default",
        asound_cards: Path | str = "/proc/asound/cards",
    ) -> None:
        self.device = device
        self._asound_cards = Path(asound_cards)
        self._closed = False

    def prepare(self) -> None:
        status = self.status()
        if not status.available:
            raise RuntimeError(status.detail or "ALSA audio output is unavailable")

    def status(self) -> AudioOutputStatus:
        if self._closed:
            return AudioOutputStatus(False, self.device, "audio output is closed")
        try:
            cards = self._asound_cards.read_text(encoding="utf-8")
        except OSError as exc:
            return AudioOutputStatus(False, self.device, str(exc))
        available = bool(cards.strip()) and "no soundcards" not in cards.lower()
        detail = None if available else "no ALSA sound cards detected"
        return AudioOutputStatus(available, self.device, detail)

    def close(self) -> None:
        self._closed = True


RaspberryPiAudioOutput = Max98357aAudioOutput
