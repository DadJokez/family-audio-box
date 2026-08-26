"""Hardware abstraction interfaces used by FamilyBox.

The interfaces are deliberately synchronous.  Raspberry Pi drivers are mostly
blocking APIs, so application services move these calls to worker threads when
they run inside an asyncio event loop.  This also keeps the fake adapters useful
from small scripts and unit tests.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from typing import TypeAlias

UidValue: TypeAlias = str | bytes | bytearray | memoryview


def normalize_uid(value: UidValue) -> str:
    """Return a stable, separator-free uppercase NFC UID.

    PN532 libraries return byte sequences, while administration paths often
    receive strings.  Normalizing both at the hardware boundary prevents the
    same physical tag from acquiring multiple database identities.
    """

    if isinstance(value, str):
        candidate = value.strip()
        if candidate.lower().startswith("0x"):
            candidate = candidate[2:]
        compact = re.sub(r"[:\-\s]", "", candidate)
        if not compact or len(compact) % 2 or not re.fullmatch(r"[0-9a-fA-F]+", compact):
            raise ValueError(f"invalid NFC UID: {value!r}")
        raw = bytes.fromhex(compact)
    else:
        raw = bytes(value)
        if not raw:
            raise ValueError("NFC UID cannot be empty")

    return raw.hex().upper()


class ButtonAction(StrEnum):
    PREVIOUS = "previous"
    PLAY_PAUSE = "play_pause"
    NEXT = "next"


@dataclass(frozen=True, slots=True)
class VolumeEvent:
    """A rotary movement or push from the volume control."""

    delta: int = 0
    pressed: bool = False

    def __post_init__(self) -> None:
        if self.delta == 0 and not self.pressed:
            raise ValueError("a volume event must contain movement or a press")


@dataclass(frozen=True, slots=True)
class PowerStatus:
    external_power: bool | None = None
    battery_percent: float | None = None
    shutdown_requested: bool = False


@dataclass(frozen=True, slots=True)
class AudioOutputStatus:
    available: bool
    device: str
    detail: str | None = None


class NfcReader(ABC):
    @abstractmethod
    def read_uid(self, timeout_seconds: float = 0.2) -> str | None:
        """Return the currently visible tag UID, or ``None`` when absent."""

    @abstractmethod
    def close(self) -> None:
        """Release hardware resources."""


class ButtonController(ABC):
    @abstractmethod
    def read_action(self, timeout_seconds: float = 0.2) -> ButtonAction | None:
        """Wait for a physical button action."""

    @abstractmethod
    def close(self) -> None:
        """Release hardware resources."""


class VolumeController(ABC):
    @abstractmethod
    def read_event(self, timeout_seconds: float = 0.2) -> VolumeEvent | None:
        """Wait for a rotary movement or encoder push."""

    @abstractmethod
    def close(self) -> None:
        """Release hardware resources."""


class PowerMonitor(ABC):
    @abstractmethod
    def status(self) -> PowerStatus:
        """Return the power information that is available on this platform."""

    @abstractmethod
    def close(self) -> None:
        """Release hardware resources."""


class AudioOutput(ABC):
    @abstractmethod
    def prepare(self) -> None:
        """Prepare the configured audio output for playback."""

    @abstractmethod
    def status(self) -> AudioOutputStatus:
        """Describe whether the output appears usable."""

    @abstractmethod
    def close(self) -> None:
        """Release hardware resources."""
