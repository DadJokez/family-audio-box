"""Local filesystem content provider."""

from __future__ import annotations

import json
import os
import re
import shutil
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

from familybox.content.base import (
    ContentProvider,
    ContentRepository,
    PlayableContent,
    PlayableTrack,
)
from familybox.domain.models import Content, ContentTrack, ContentType, new_id

SUPPORTED_AUDIO_EXTENSIONS = frozenset({".mp3", ".m4a", ".m4b"})
SUPPORTED_PLAYLIST_EXTENSIONS = frozenset({".m3u", ".m3u8"})
SUPPORTED_ARTWORK_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp"})


class LocalContentError(ValueError):
    """Raised when local content cannot be safely imported or resolved."""


class LocalContentProvider(ContentProvider):
    """Import and resolve audio stored below the configured media root."""

    def __init__(self, media_root: str | Path, repository: ContentRepository) -> None:
        self.media_root = Path(media_root).expanduser().resolve()
        self.repository = repository

    @property
    def provider_name(self) -> str:
        return "local"

    def import_content(
        self,
        source: str | Path | Sequence[str | Path],
        *,
        title: str | None = None,
        artwork: str | Path | None = None,
        metadata: dict[str, Any] | None = None,
        content_type: ContentType = ContentType.AUDIOBOOK,
    ) -> Content:
        """Copy a file, folder, M3U playlist, or explicit file list into media.

        Sources are copied, never moved. The catalog is updated only after a
        complete directory has been atomically put in place.
        """

        source_items = _source_items(source)
        audio_files = self._expand_sources(source_items)
        if not audio_files:
            raise LocalContentError("No supported audio files were found")

        content_id = new_id()
        content_title = (title or _default_title(source_items)).strip()
        if not content_title:
            raise LocalContentError("Content title cannot be empty")

        self.media_root.mkdir(parents=True, exist_ok=True)
        staging = self.media_root / f".{content_id}.importing"
        destination = self.media_root / content_id
        if staging.exists() or destination.exists():
            raise FileExistsError(f"Content destination already exists: {content_id}")
        staging.mkdir(mode=0o755)

        try:
            width = max(3, len(str(len(audio_files))))
            tracks: list[ContentTrack] = []
            for index, audio_file in enumerate(audio_files):
                suffix = audio_file.suffix.lower()
                filename = f"{index + 1:0{width}d}{suffix}"
                shutil.copy2(audio_file, staging / filename)
                tracks.append(
                    ContentTrack(
                        content_id=content_id,
                        track_index=index,
                        title=audio_file.stem,
                        local_path=f"{content_id}/{filename}",
                        provider_reference=str(audio_file),
                    )
                )

            artwork_path: str | None = None
            if artwork is not None:
                artwork_source = Path(artwork).expanduser().resolve(strict=True)
                if (
                    not artwork_source.is_file()
                    or artwork_source.suffix.lower() not in SUPPORTED_ARTWORK_EXTENSIONS
                ):
                    raise LocalContentError("Artwork must be a JPEG, PNG, or WebP file")
                artwork_filename = f"cover{artwork_source.suffix.lower()}"
                shutil.copy2(artwork_source, staging / artwork_filename)
                artwork_path = f"{content_id}/{artwork_filename}"

            content = Content(
                id=content_id,
                title=content_title,
                content_type=content_type,
                provider=self.provider_name,
                provider_reference=content_id,
                local_path=content_id,
                artwork_path=artwork_path,
                metadata=dict(metadata or {}),
            )
            _write_manifest(staging / "metadata.json", content, tracks)
            os.replace(staging, destination)
            try:
                self.repository.add_content(content, tracks)
            except BaseException:
                shutil.rmtree(destination, ignore_errors=True)
                raise
            return content
        except BaseException:
            shutil.rmtree(staging, ignore_errors=True)
            raise

    def resolve(self, content: Content) -> PlayableContent:
        if content.provider != self.provider_name:
            raise LocalContentError(
                f"Provider {self.provider_name!r} cannot resolve {content.provider!r} content"
            )
        tracks = self.repository.list_content_tracks(content.id)
        playable: list[PlayableTrack] = []
        for track in tracks:
            if track.local_path is None:
                raise LocalContentError(f"Track {track.id} has no local path")
            source = self._existing_media_file(track.local_path)
            if source.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
                raise LocalContentError(f"Unsupported track format: {source.name}")
            playable.append(
                PlayableTrack(
                    id=track.id,
                    content_id=track.content_id,
                    track_index=track.track_index,
                    title=track.title,
                    source=str(source),
                    duration_seconds=track.duration_seconds,
                )
            )
        return PlayableContent(content=content, tracks=tuple(playable))

    def update_content(
        self,
        content_id: str,
        *,
        title: str,
        artwork: str | Path | None = None,
    ) -> Content:
        """Update parent-facing metadata and optionally replace cover artwork."""

        content = self.repository.get_content(content_id)
        if content is None:
            raise KeyError(f"Unknown content: {content_id}")
        if content.provider != self.provider_name or content.local_path is None:
            raise LocalContentError("Content is not managed by the local provider")
        clean_title = title.strip()
        if not clean_title:
            raise LocalContentError("Content title cannot be empty")

        directory = self._media_path(content.local_path)
        if directory.parent != self.media_root or directory.name != content.id:
            raise LocalContentError("Local content directory is not canonical")

        artwork_path = content.artwork_path
        staged_artwork: Path | None = None
        final_artwork: Path | None = None
        if artwork is not None:
            source = Path(artwork).expanduser().resolve(strict=True)
            if not source.is_file() or source.suffix.lower() not in SUPPORTED_ARTWORK_EXTENSIONS:
                raise LocalContentError("Artwork must be a JPEG, PNG, or WebP file")
            final_artwork = directory / f"cover{source.suffix.lower()}"
            staged_artwork = directory / f".{final_artwork.name}.uploading"
            shutil.copy2(source, staged_artwork)
            artwork_path = f"{content.id}/{final_artwork.name}"

        updated = replace(content, title=clean_title, artwork_path=artwork_path)
        try:
            self.repository.update_content(updated)
        except BaseException:
            if staged_artwork is not None:
                staged_artwork.unlink(missing_ok=True)
            raise

        if staged_artwork is not None and final_artwork is not None:
            try:
                os.replace(staged_artwork, final_artwork)
            except BaseException:
                self.repository.update_content(content)
                staged_artwork.unlink(missing_ok=True)
                raise

        if content.artwork_path and content.artwork_path != artwork_path:
            previous = self._media_path(content.artwork_path)
            if previous.parent == directory:
                previous.unlink(missing_ok=True)
        _write_manifest(
            directory / "metadata.json",
            updated,
            self.repository.list_content_tracks(content.id),
        )
        return updated

    def delete(self, content_id: str) -> bool:
        """Delete local content without permitting paths outside media_root."""

        content = self.repository.get_content(content_id)
        if content is None:
            return False
        if content.provider != self.provider_name:
            raise LocalContentError("Refusing to delete content owned by another provider")
        if content.local_path is None:
            raise LocalContentError("Local content has no media directory")

        target = self._media_path(content.local_path)
        if target.parent != self.media_root or target.name != content.id:
            raise LocalContentError("Refusing to delete a non-canonical local content directory")
        if not target.exists():
            return self.repository.delete_content(content.id)
        if not target.is_dir() or target.is_symlink():
            raise LocalContentError("Local content path is not a safe directory")

        tombstone = self.media_root / f".{content.id}.deleting"
        if tombstone.exists():
            raise LocalContentError(f"Deletion already in progress for {content.id}")
        os.replace(target, tombstone)
        try:
            deleted = self.repository.delete_content(content.id)
            if not deleted:
                os.replace(tombstone, target)
                return False
        except BaseException:
            os.replace(tombstone, target)
            raise
        shutil.rmtree(tombstone)
        return True

    def _expand_sources(self, sources: Sequence[Path]) -> list[Path]:
        audio_files: list[Path] = []
        for source in sources:
            resolved = source.expanduser().resolve(strict=True)
            if resolved.is_dir():
                audio_files.extend(
                    sorted(
                        (
                            item.resolve(strict=True)
                            for item in resolved.rglob("*")
                            if item.is_file() and item.suffix.lower() in SUPPORTED_AUDIO_EXTENSIONS
                        ),
                        key=lambda item: _natural_key(str(item.relative_to(resolved))),
                    )
                )
            elif resolved.suffix.lower() in SUPPORTED_PLAYLIST_EXTENSIONS:
                audio_files.extend(self._read_playlist(resolved))
            elif resolved.is_file() and resolved.suffix.lower() in SUPPORTED_AUDIO_EXTENSIONS:
                audio_files.append(resolved)
            else:
                raise LocalContentError(f"Unsupported local content: {source}")
        return audio_files

    def _read_playlist(self, playlist: Path) -> list[Path]:
        tracks: list[Path] = []
        try:
            lines = playlist.read_text(encoding="utf-8-sig").splitlines()
        except UnicodeDecodeError as exc:
            raise LocalContentError(f"Playlist is not UTF-8: {playlist}") from exc
        for raw_line in lines:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "://" in line or line.lower().startswith("file:"):
                raise LocalContentError(f"Remote or URI playlist entries are not supported: {line}")
            candidate = Path(line).expanduser()
            if not candidate.is_absolute():
                candidate = playlist.parent / candidate
            try:
                candidate = candidate.resolve(strict=True)
            except FileNotFoundError as exc:
                raise LocalContentError(f"Playlist entry does not exist: {line}") from exc
            if (
                not candidate.is_file()
                or candidate.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS
            ):
                raise LocalContentError(f"Unsupported playlist entry: {line}")
            tracks.append(candidate)
        return tracks

    def _media_path(self, stored_path: str) -> Path:
        candidate = Path(stored_path)
        if not candidate.is_absolute():
            candidate = self.media_root / candidate
        resolved = candidate.resolve()
        if resolved == self.media_root or not resolved.is_relative_to(self.media_root):
            raise LocalContentError("Media path escapes the configured media root")
        return resolved

    def _existing_media_file(self, stored_path: str) -> Path:
        resolved = self._media_path(stored_path)
        if not resolved.is_file():
            raise LocalContentError(f"Local audio file is missing: {stored_path}")
        return resolved


def _source_items(
    source: str | Path | Sequence[str | Path],
) -> list[Path]:
    if isinstance(source, (str, Path)):
        return [Path(source)]
    items = [Path(item) for item in source]
    if not items:
        raise LocalContentError("At least one source is required")
    return items


def _default_title(sources: Sequence[Path]) -> str:
    if len(sources) != 1:
        return "Imported audio"
    source = sources[0].expanduser()
    if source.suffix.lower() in SUPPORTED_PLAYLIST_EXTENSIONS or source.is_file():
        return source.stem
    return source.name


def _natural_key(value: str) -> tuple[object, ...]:
    return tuple(
        int(part) if part.isdigit() else part.casefold() for part in re.split(r"(\d+)", value)
    )


def _write_manifest(path: Path, content: Content, tracks: Sequence[ContentTrack]) -> None:
    manifest = {
        "schema_version": 1,
        "id": content.id,
        "title": content.title,
        "content_type": content.content_type.value,
        "provider": content.provider,
        "metadata": content.metadata,
        "tracks": [
            {
                "id": track.id,
                "index": track.track_index,
                "title": track.title,
                "path": track.local_path,
            }
            for track in tracks
        ],
    }
    try:
        encoded = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise LocalContentError("Content metadata must be JSON serializable") from exc
    path.write_text(f"{encoded}\n", encoding="utf-8")
