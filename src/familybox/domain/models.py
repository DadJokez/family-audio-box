"""Domain models shared by services, providers, and persistence.

The domain deliberately contains no Raspberry Pi, mpv, HTTP, or SQLite details.
Identifiers are UUID strings so records can later be synchronized without a
central ID allocator.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

_UID_PATTERN = re.compile(r"^[0-9A-F]+$")


def new_id() -> str:
    """Return a synchronization-friendly opaque identifier."""

    return str(uuid4())


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(UTC)


def normalize_uid(uid: str | bytes) -> str:
    """Return a canonical, separator-free uppercase NFC UID.

    Readers commonly report the same UID as bytes, colon-separated hex, or
    space-separated hex. Keeping one representation prevents duplicate tag
    assignments.
    """

    value = uid.hex() if isinstance(uid, bytes) else re.sub(r"[\s:\-]", "", uid)
    value = value.upper()
    if not value or len(value) % 2 or not _UID_PATTERN.fullmatch(value):
        raise ValueError(f"Invalid NFC UID: {uid!r}")
    return value


class ContentType(StrEnum):
    AUDIOBOOK = "audiobook"
    MUSIC = "music"
    PLAYLIST = "playlist"
    AUDIO = "audio"


@dataclass(frozen=True, slots=True, kw_only=True)
class Child:
    id: str = field(default_factory=new_id)
    name: str
    settings: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True, slots=True, kw_only=True)
class Device:
    id: str = field(default_factory=new_id)
    name: str
    child_id: str | None = None
    created_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True, slots=True, kw_only=True)
class Content:
    id: str = field(default_factory=new_id)
    title: str
    content_type: ContentType = ContentType.AUDIOBOOK
    provider: str
    provider_reference: str
    local_path: str | None = None
    artwork_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True, slots=True, kw_only=True)
class ContentTrack:
    id: str = field(default_factory=new_id)
    content_id: str
    track_index: int
    title: str
    local_path: str | None = None
    provider_reference: str | None = None
    duration_seconds: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.track_index < 0:
            raise ValueError("track_index must be non-negative")
        if self.duration_seconds is not None and self.duration_seconds < 0:
            raise ValueError("duration_seconds must be non-negative")


@dataclass(frozen=True, slots=True, kw_only=True)
class Tag:
    uid: str
    content_id: str
    name: str | None = None
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(self, "uid", normalize_uid(self.uid))


@dataclass(frozen=True, slots=True, kw_only=True)
class UnknownTagObservation:
    uid: str
    first_seen_at: datetime
    last_seen_at: datetime
    detection_count: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "uid", normalize_uid(self.uid))
        if self.detection_count < 1:
            raise ValueError("detection_count must be positive")


@dataclass(frozen=True, slots=True, kw_only=True)
class PlaybackState:
    device_id: str
    content_id: str
    track_index: int = 0
    position_seconds: float = 0.0
    completed: bool = False
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if self.track_index < 0:
            raise ValueError("track_index must be non-negative")
        if self.position_seconds < 0:
            raise ValueError("position_seconds must be non-negative")
