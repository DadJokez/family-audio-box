from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from familybox.domain.models import (
    Child,
    Content,
    ContentTrack,
    Device,
    PlaybackState,
)
from familybox.persistence.database import Database


@pytest.fixture
def database(tmp_path):
    with Database(tmp_path / "familybox.db") as repository:
        yield repository


def test_initializes_with_wal_foreign_keys_and_one_migration(database):
    connection = database.connection

    assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert [
        row["version"] for row in connection.execute("SELECT version FROM schema_migrations")
    ] == ["0001_initial"]


def test_content_tracks_are_ordered_and_cascade(database):
    content = Content(
        title="Bedtime Stories",
        provider="local",
        provider_reference="bedtime",
        metadata={"author": "A. Reader"},
    )
    later = ContentTrack(
        content_id=content.id,
        track_index=1,
        title="Chapter 2",
        local_path=f"{content.id}/002.m4b",
    )
    first = ContentTrack(
        content_id=content.id,
        track_index=0,
        title="Chapter 1",
        local_path=f"{content.id}/001.mp3",
    )

    database.add_content(content, [later, first])

    assert database.get_content(content.id) == content
    assert database.list_content_tracks(content.id) == [first, later]
    assert database.delete_content(content.id) is True
    assert database.list_content_tracks(content.id) == []


def test_foreign_keys_reject_orphaned_tracks(database):
    orphan = ContentTrack(
        content_id="missing-content",
        track_index=0,
        title="Nowhere",
        local_path="missing/001.mp3",
    )

    with pytest.raises(sqlite3.IntegrityError):
        database.connection.execute(
            """
            INSERT INTO content_tracks(
                id, content_id, track_index, title, local_path,
                provider_reference, duration_seconds, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                orphan.id,
                orphan.content_id,
                orphan.track_index,
                orphan.title,
                orphan.local_path,
                None,
                None,
                "{}",
            ),
        )


def test_unknown_tag_observation_and_assignment_are_immediate(database):
    content = Content(
        title="The Wind in the Willows",
        provider="local",
        provider_reference="wind-willows",
    )
    database.add_content(content)
    first_seen = datetime(2026, 1, 1, tzinfo=UTC)

    first = database.observe_unknown_tag("04:a1-b2 c3", observed_at=first_seen)
    second = database.observe_unknown_tag(
        b"\x04\xa1\xb2\xc3", observed_at=first_seen + timedelta(seconds=5)
    )

    assert first is not None
    assert first.uid == "04A1B2C3"
    assert second is not None
    assert second.detection_count == 2
    assert database.get_last_unknown_tag() == second

    tag = database.assign_tag("04:A1:B2:C3", content.id, "Mole")

    assert tag.uid == "04A1B2C3"
    assert database.resolve_tag(b"\x04\xa1\xb2\xc3") == content
    assert database.get_last_unknown_tag() is None
    assert database.observe_unknown_tag(tag.uid) is None


def test_playback_progress_is_scoped_to_device(database):
    child_a = Child(name="Ari")
    child_b = Child(name="Bea")
    database.save_child(child_a)
    database.save_child(child_b)
    device_a = Device(name="Ari's Box", child_id=child_a.id)
    device_b = Device(name="Bea's Box", child_id=child_b.id)
    database.save_device(device_a)
    database.save_device(device_b)
    content = Content(
        title="Treasure Island",
        provider="local",
        provider_reference="treasure-island",
    )
    database.add_content(content)
    state_a = PlaybackState(
        device_id=device_a.id,
        content_id=content.id,
        track_index=3,
        position_seconds=42.5,
    )
    state_b = PlaybackState(
        device_id=device_b.id,
        content_id=content.id,
        track_index=1,
        position_seconds=9.0,
    )

    database.save_playback_state(state_a)
    database.save_playback_state(state_b)

    assert database.get_playback_state(device_a.id, content.id) == state_a
    assert database.get_playback_state(device_b.id, content.id) == state_b

    advanced_a = PlaybackState(
        device_id=device_a.id,
        content_id=content.id,
        track_index=4,
        position_seconds=3.25,
    )
    database.save_playback_state(advanced_a)

    assert database.get_playback_state(device_a.id, content.id) == advanced_a
    assert database.get_playback_state(device_b.id, content.id) == state_b


def test_initialization_is_idempotent(tmp_path):
    path = tmp_path / "familybox.db"
    with Database(path) as first:
        first.save_child(Child(name="Casey"))

    with Database(path) as reopened:
        assert len(reopened.list_children()) == 1
        assert (
            reopened.connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 1
        )
