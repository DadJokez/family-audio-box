"""Provider boundary for content that can be handed to playback."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from familybox.domain.models import Content, ContentTrack


@dataclass(frozen=True, slots=True)
class PlayableTrack:
    """A provider-neutral source that mpv can play."""

    id: str
    content_id: str
    track_index: int
    title: str
    source: str
    duration_seconds: float | None = None


@dataclass(frozen=True, slots=True)
class PlayableContent:
    content: Content
    tracks: tuple[PlayableTrack, ...]

    def __post_init__(self) -> None:
        if not self.tracks:
            raise ValueError("playable content must contain at least one track")


class ContentRepository(Protocol):
    """Persistence operations needed by filesystem-backed content."""

    def add_content(self, content: Content, tracks: Sequence[ContentTrack] = ()) -> Content: ...

    def get_content(self, content_id: str) -> Content | None: ...

    def update_content(self, content: Content) -> Content: ...

    def list_content_tracks(self, content_id: str) -> list[ContentTrack]: ...

    def delete_content(self, content_id: str) -> bool: ...


class ContentProvider(ABC):
    """Common provider interface; playback does not depend on provider details."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Stable name persisted on :class:`~familybox.domain.models.Content`."""

    @abstractmethod
    def resolve(self, content: Content) -> PlayableContent:
        """Resolve a catalog item into an ordered, playable queue."""
