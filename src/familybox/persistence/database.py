"""Small stdlib SQLite repository for FamilyBox.

The repository owns a single connection and serializes access. This is a good
fit for a single-purpose appliance and avoids needing an ORM or connection
pool. WAL allows readers to proceed while the application persists progress.
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any

from familybox.domain.models import (
    Child,
    Content,
    ContentTrack,
    ContentType,
    Device,
    PlaybackState,
    Tag,
    UnknownTagObservation,
    normalize_uid,
    utc_now,
)

_MIGRATION_NAME = re.compile(r"^[0-9][0-9A-Za-z_.-]*$")


class DatabaseNotInitializedError(RuntimeError):
    pass


class Database:
    """SQLite-backed repository with explicit migrations and domain results."""

    def __init__(
        self,
        path: str | Path,
        *,
        migrations_dir: str | Path | None = None,
    ) -> None:
        self.path = Path(path) if str(path) != ":memory:" else Path(":memory:")
        self.migrations_dir = (
            Path(migrations_dir)
            if migrations_dir is not None
            else Path(__file__).with_name("migrations")
        )
        self._connection: sqlite3.Connection | None = None
        self._lock = RLock()

    @property
    def connection(self) -> sqlite3.Connection:
        if self._connection is None:
            raise DatabaseNotInitializedError("Database.initialize() must be called before use")
        return self._connection

    def initialize(self) -> Database:
        """Open the database, configure SQLite, and apply pending migrations."""

        with self._lock:
            if self._connection is not None:
                return self
            if self.path != Path(":memory:"):
                self.path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(str(self.path), timeout=10, check_same_thread=False)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA busy_timeout = 10000")
            connection.execute("PRAGMA synchronous = NORMAL")
            connection.execute("PRAGMA journal_mode = WAL")
            self._connection = connection
            try:
                self._apply_migrations()
            except Exception:
                connection.close()
                self._connection = None
                raise
        return self

    def close(self) -> None:
        with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None

    def __enter__(self) -> Database:
        return self.initialize()

    def __exit__(self, *_: object) -> None:
        self.close()

    def _apply_migrations(self) -> None:
        connection = self.connection
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
            """
        )
        applied = {
            row["version"] for row in connection.execute("SELECT version FROM schema_migrations")
        }
        for migration in sorted(self.migrations_dir.glob("*.sql")):
            version = migration.stem
            if not _MIGRATION_NAME.fullmatch(version):
                raise ValueError(f"Invalid migration filename: {migration.name}")
            if version in applied:
                continue
            # executescript does not accept bound parameters. The filename is
            # strictly validated above before it is interpolated.
            applied_at = _to_db_datetime(utc_now())
            script = migration.read_text(encoding="utf-8")
            connection.executescript(
                "BEGIN IMMEDIATE;\n"
                f"{script}\n"
                "INSERT INTO schema_migrations(version, applied_at) "
                f"VALUES ('{version}', '{applied_at}');\n"
                "COMMIT;"
            )

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Run a short write transaction on the serialized connection."""

        with self._lock:
            connection = self.connection
            connection.execute("BEGIN IMMEDIATE")
            try:
                yield connection
            except BaseException:
                connection.rollback()
                raise
            else:
                connection.commit()

    def save_child(self, child: Child) -> Child:
        with self.transaction() as connection:
            connection.execute(
                """
                INSERT INTO children(id, name, settings_json, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    settings_json = excluded.settings_json
                """,
                (
                    child.id,
                    child.name,
                    _dump_json(child.settings),
                    _to_db_datetime(child.created_at),
                ),
            )
        return child

    def get_child(self, child_id: str) -> Child | None:
        with self._lock:
            row = self.connection.execute(
                "SELECT * FROM children WHERE id = ?", (child_id,)
            ).fetchone()
        return _child_from_row(row) if row else None

    def list_children(self) -> list[Child]:
        with self._lock:
            rows = self.connection.execute(
                "SELECT * FROM children ORDER BY name COLLATE NOCASE, id"
            ).fetchall()
        return [_child_from_row(row) for row in rows]

    def save_device(self, device: Device) -> Device:
        with self.transaction() as connection:
            connection.execute(
                """
                INSERT INTO devices(id, name, child_id, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    child_id = excluded.child_id
                """,
                (
                    device.id,
                    device.name,
                    device.child_id,
                    _to_db_datetime(device.created_at),
                ),
            )
        return device

    def get_device(self, device_id: str) -> Device | None:
        with self._lock:
            row = self.connection.execute(
                "SELECT * FROM devices WHERE id = ?", (device_id,)
            ).fetchone()
        return _device_from_row(row) if row else None

    def list_devices(self) -> list[Device]:
        with self._lock:
            rows = self.connection.execute(
                "SELECT * FROM devices ORDER BY name COLLATE NOCASE, id"
            ).fetchall()
        return [_device_from_row(row) for row in rows]

    def add_content(self, content: Content, tracks: Sequence[ContentTrack] = ()) -> Content:
        _validate_tracks(content.id, tracks)
        with self.transaction() as connection:
            connection.execute(
                """
                INSERT INTO content(
                    id, title, content_type, provider, provider_reference,
                    local_path, artwork_path, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                _content_values(content),
            )
            connection.executemany(
                """
                INSERT INTO content_tracks(
                    id, content_id, track_index, title, local_path,
                    provider_reference, duration_seconds, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [_track_values(track) for track in tracks],
            )
        return content

    def update_content(self, content: Content) -> Content:
        with self.transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE content SET
                    title = ?, content_type = ?, provider = ?,
                    provider_reference = ?, local_path = ?, artwork_path = ?,
                    metadata_json = ?
                WHERE id = ?
                """,
                (
                    content.title,
                    content.content_type.value,
                    content.provider,
                    content.provider_reference,
                    content.local_path,
                    content.artwork_path,
                    _dump_json(content.metadata),
                    content.id,
                ),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"Unknown content: {content.id}")
        return content

    def get_content(self, content_id: str) -> Content | None:
        with self._lock:
            row = self.connection.execute(
                "SELECT * FROM content WHERE id = ?", (content_id,)
            ).fetchone()
        return _content_from_row(row) if row else None

    def list_content(self) -> list[Content]:
        with self._lock:
            rows = self.connection.execute(
                "SELECT * FROM content ORDER BY title COLLATE NOCASE, id"
            ).fetchall()
        return [_content_from_row(row) for row in rows]

    def delete_content(self, content_id: str) -> bool:
        with self.transaction() as connection:
            cursor = connection.execute("DELETE FROM content WHERE id = ?", (content_id,))
        return cursor.rowcount > 0

    def replace_content_tracks(self, content_id: str, tracks: Sequence[ContentTrack]) -> None:
        _validate_tracks(content_id, tracks)
        with self.transaction() as connection:
            exists = connection.execute(
                "SELECT 1 FROM content WHERE id = ?", (content_id,)
            ).fetchone()
            if not exists:
                raise KeyError(f"Unknown content: {content_id}")
            connection.execute("DELETE FROM content_tracks WHERE content_id = ?", (content_id,))
            connection.executemany(
                """
                INSERT INTO content_tracks(
                    id, content_id, track_index, title, local_path,
                    provider_reference, duration_seconds, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [_track_values(track) for track in tracks],
            )

    def list_content_tracks(self, content_id: str) -> list[ContentTrack]:
        with self._lock:
            rows = self.connection.execute(
                """
                SELECT * FROM content_tracks
                WHERE content_id = ?
                ORDER BY track_index, id
                """,
                (content_id,),
            ).fetchall()
        return [_track_from_row(row) for row in rows]

    def assign_tag(
        self,
        uid: str | bytes,
        content_id: str,
        name: str | None = None,
        *,
        created_at: datetime | None = None,
    ) -> Tag:
        tag = Tag(
            uid=normalize_uid(uid),
            content_id=content_id,
            name=name,
            created_at=created_at or utc_now(),
        )
        with self.transaction() as connection:
            connection.execute(
                """
                INSERT INTO tags(uid, content_id, name, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(uid) DO UPDATE SET
                    content_id = excluded.content_id,
                    name = excluded.name,
                    created_at = excluded.created_at
                """,
                (tag.uid, tag.content_id, tag.name, _to_db_datetime(tag.created_at)),
            )
            connection.execute("DELETE FROM unknown_tags WHERE uid = ?", (tag.uid,))
        return tag

    def get_tag(self, uid: str | bytes) -> Tag | None:
        canonical_uid = normalize_uid(uid)
        with self._lock:
            row = self.connection.execute(
                "SELECT * FROM tags WHERE uid = ?", (canonical_uid,)
            ).fetchone()
        return _tag_from_row(row) if row else None

    def list_tags(self) -> list[Tag]:
        with self._lock:
            rows = self.connection.execute(
                "SELECT * FROM tags ORDER BY name COLLATE NOCASE, uid"
            ).fetchall()
        return [_tag_from_row(row) for row in rows]

    def unassign_tag(self, uid: str | bytes) -> bool:
        canonical_uid = normalize_uid(uid)
        with self.transaction() as connection:
            cursor = connection.execute("DELETE FROM tags WHERE uid = ?", (canonical_uid,))
        return cursor.rowcount > 0

    def resolve_tag(self, uid: str | bytes) -> Content | None:
        canonical_uid = normalize_uid(uid)
        with self._lock:
            row = self.connection.execute(
                """
                SELECT content.* FROM content
                JOIN tags ON tags.content_id = content.id
                WHERE tags.uid = ?
                """,
                (canonical_uid,),
            ).fetchone()
        return _content_from_row(row) if row else None

    def observe_unknown_tag(
        self, uid: str | bytes, *, observed_at: datetime | None = None
    ) -> UnknownTagObservation | None:
        canonical_uid = normalize_uid(uid)
        timestamp = _to_db_datetime(observed_at or utc_now())
        with self.transaction() as connection:
            known = connection.execute(
                "SELECT 1 FROM tags WHERE uid = ?", (canonical_uid,)
            ).fetchone()
            if known:
                return None
            connection.execute(
                """
                INSERT INTO unknown_tags(
                    uid, first_seen_at, last_seen_at, detection_count
                ) VALUES (?, ?, ?, 1)
                ON CONFLICT(uid) DO UPDATE SET
                    last_seen_at = excluded.last_seen_at,
                    detection_count = unknown_tags.detection_count + 1
                """,
                (canonical_uid, timestamp, timestamp),
            )
            row = connection.execute(
                "SELECT * FROM unknown_tags WHERE uid = ?", (canonical_uid,)
            ).fetchone()
        assert row is not None
        return _unknown_tag_from_row(row)

    def get_last_unknown_tag(self) -> UnknownTagObservation | None:
        with self._lock:
            row = self.connection.execute(
                """
                SELECT * FROM unknown_tags
                ORDER BY last_seen_at DESC, uid
                LIMIT 1
                """
            ).fetchone()
        return _unknown_tag_from_row(row) if row else None

    def list_unknown_tags(self) -> list[UnknownTagObservation]:
        with self._lock:
            rows = self.connection.execute(
                "SELECT * FROM unknown_tags ORDER BY last_seen_at DESC, uid"
            ).fetchall()
        return [_unknown_tag_from_row(row) for row in rows]

    def save_playback_state(self, state: PlaybackState) -> PlaybackState:
        with self.transaction() as connection:
            connection.execute(
                """
                INSERT INTO playback_state(
                    device_id, content_id, track_index, position_seconds,
                    completed, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(device_id, content_id) DO UPDATE SET
                    track_index = excluded.track_index,
                    position_seconds = excluded.position_seconds,
                    completed = excluded.completed,
                    updated_at = excluded.updated_at
                """,
                (
                    state.device_id,
                    state.content_id,
                    state.track_index,
                    state.position_seconds,
                    int(state.completed),
                    _to_db_datetime(state.updated_at),
                ),
            )
        return state

    def get_playback_state(self, device_id: str, content_id: str) -> PlaybackState | None:
        with self._lock:
            row = self.connection.execute(
                """
                SELECT * FROM playback_state
                WHERE device_id = ? AND content_id = ?
                """,
                (device_id, content_id),
            ).fetchone()
        return _playback_state_from_row(row) if row else None


def _validate_tracks(content_id: str, tracks: Sequence[ContentTrack]) -> None:
    indexes: set[int] = set()
    for track in tracks:
        if track.content_id != content_id:
            raise ValueError(f"Track {track.id} belongs to {track.content_id}, not {content_id}")
        if track.track_index in indexes:
            raise ValueError(f"Duplicate track_index: {track.track_index}")
        indexes.add(track.track_index)


def _content_values(content: Content) -> tuple[Any, ...]:
    return (
        content.id,
        content.title,
        content.content_type.value,
        content.provider,
        content.provider_reference,
        content.local_path,
        content.artwork_path,
        _dump_json(content.metadata),
        _to_db_datetime(content.created_at),
    )


def _track_values(track: ContentTrack) -> tuple[Any, ...]:
    return (
        track.id,
        track.content_id,
        track.track_index,
        track.title,
        track.local_path,
        track.provider_reference,
        track.duration_seconds,
        _dump_json(track.metadata),
    )


def _dump_json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _load_json(value: str) -> dict[str, Any]:
    loaded = json.loads(value)
    if not isinstance(loaded, dict):
        raise ValueError("Persisted metadata must be a JSON object")
    return loaded


def _to_db_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat(timespec="microseconds")


def _from_db_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _child_from_row(row: sqlite3.Row) -> Child:
    return Child(
        id=row["id"],
        name=row["name"],
        settings=_load_json(row["settings_json"]),
        created_at=_from_db_datetime(row["created_at"]),
    )


def _device_from_row(row: sqlite3.Row) -> Device:
    return Device(
        id=row["id"],
        name=row["name"],
        child_id=row["child_id"],
        created_at=_from_db_datetime(row["created_at"]),
    )


def _content_from_row(row: sqlite3.Row) -> Content:
    return Content(
        id=row["id"],
        title=row["title"],
        content_type=ContentType(row["content_type"]),
        provider=row["provider"],
        provider_reference=row["provider_reference"],
        local_path=row["local_path"],
        artwork_path=row["artwork_path"],
        metadata=_load_json(row["metadata_json"]),
        created_at=_from_db_datetime(row["created_at"]),
    )


def _track_from_row(row: sqlite3.Row) -> ContentTrack:
    return ContentTrack(
        id=row["id"],
        content_id=row["content_id"],
        track_index=row["track_index"],
        title=row["title"],
        local_path=row["local_path"],
        provider_reference=row["provider_reference"],
        duration_seconds=row["duration_seconds"],
        metadata=_load_json(row["metadata_json"]),
    )


def _tag_from_row(row: sqlite3.Row) -> Tag:
    return Tag(
        uid=row["uid"],
        content_id=row["content_id"],
        name=row["name"],
        created_at=_from_db_datetime(row["created_at"]),
    )


def _unknown_tag_from_row(row: sqlite3.Row) -> UnknownTagObservation:
    return UnknownTagObservation(
        uid=row["uid"],
        first_seen_at=_from_db_datetime(row["first_seen_at"]),
        last_seen_at=_from_db_datetime(row["last_seen_at"]),
        detection_count=row["detection_count"],
    )


def _playback_state_from_row(row: sqlite3.Row) -> PlaybackState:
    return PlaybackState(
        device_id=row["device_id"],
        content_id=row["content_id"],
        track_index=row["track_index"],
        position_seconds=row["position_seconds"],
        completed=bool(row["completed"]),
        updated_at=_from_db_datetime(row["updated_at"]),
    )
