"""Events emitted by the hardware-facing services."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from .models import normalize_uid, utc_now


class Button(StrEnum):
    PREVIOUS = "previous"
    PLAY_PAUSE = "play_pause"
    NEXT = "next"
    VOLUME_PUSH = "volume_push"


@dataclass(frozen=True, slots=True, kw_only=True)
class TagPresent:
    uid: str
    occurred_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(self, "uid", normalize_uid(self.uid))


@dataclass(frozen=True, slots=True, kw_only=True)
class TagRemoved:
    uid: str
    occurred_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(self, "uid", normalize_uid(self.uid))


@dataclass(frozen=True, slots=True, kw_only=True)
class UnknownTag:
    uid: str
    occurred_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(self, "uid", normalize_uid(self.uid))


@dataclass(frozen=True, slots=True, kw_only=True)
class ButtonPressed:
    button: Button
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True, slots=True, kw_only=True)
class VolumeChanged:
    value: int
    occurred_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if not 0 <= self.value <= 100:
            raise ValueError("volume must be between 0 and 100")


PlayerEvent = TagPresent | TagRemoved | UnknownTag | ButtonPressed | VolumeChanged
