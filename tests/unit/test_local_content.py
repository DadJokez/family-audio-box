from __future__ import annotations

import json

import pytest

from familybox.content.local import LocalContentError, LocalContentProvider
from familybox.domain.models import Content
from familybox.persistence.database import Database


@pytest.fixture
def local_provider(tmp_path):
    with Database(tmp_path / "data" / "familybox.db") as repository:
        yield (
            LocalContentProvider(tmp_path / "media", repository),
            repository,
            tmp_path,
        )


def test_imports_folder_in_natural_order_and_resolves_absolute_paths(
    local_provider,
):
    provider, repository, tmp_path = local_provider
    source = tmp_path / "The Railway Children"
    source.mkdir()
    (source / "chapter10.mp3").write_bytes(b"chapter ten")
    (source / "chapter2.m4a").write_bytes(b"chapter two")
    (source / "notes.txt").write_text("not audio", encoding="utf-8")
    artwork = tmp_path / "cover.jpg"
    artwork.write_bytes(b"jpeg placeholder")

    content = provider.import_content(
        source,
        artwork=artwork,
        metadata={"author": "E. Nesbit"},
    )
    playable = provider.resolve(content)

    assert content.title == "The Railway Children"
    assert content.local_path == content.id
    assert [track.title for track in playable.tracks] == [
        "chapter2",
        "chapter10",
    ]
    assert [track.source.rsplit("/", 1)[-1] for track in playable.tracks] == [
        "001.m4a",
        "002.mp3",
    ]
    assert all(track.source.startswith(str(provider.media_root)) for track in playable.tracks)
    assert repository.get_content(content.id) == content
    manifest = json.loads(
        (provider.media_root / content.id / "metadata.json").read_text(encoding="utf-8")
    )
    assert manifest["metadata"] == {"author": "E. Nesbit"}
    assert len(manifest["tracks"]) == 2
    assert (provider.media_root / content.id / "cover.jpg").is_file()


def test_imports_m3u_playlist_in_declared_order(local_provider):
    provider, _, tmp_path = local_provider
    source = tmp_path / "source"
    source.mkdir()
    (source / "one.mp3").write_bytes(b"one")
    (source / "two.m4b").write_bytes(b"two")
    playlist = source / "favorites.m3u8"
    playlist.write_text("#EXTM3U\ntwo.m4b\n# a comment\none.mp3\n", encoding="utf-8")

    content = provider.import_content(playlist, title="Favorites")

    assert [track.title for track in provider.resolve(content).tracks] == [
        "two",
        "one",
    ]


def test_rejects_remote_playlist_entries_without_partial_import(local_provider):
    provider, repository, tmp_path = local_provider
    playlist = tmp_path / "remote.m3u"
    playlist.write_text("https://example.test/story.mp3\n", encoding="utf-8")

    with pytest.raises(LocalContentError, match="Remote or URI"):
        provider.import_content(playlist)

    assert repository.list_content() == []
    assert not provider.media_root.exists()


def test_delete_removes_catalog_and_only_its_canonical_directory(local_provider):
    provider, repository, tmp_path = local_provider
    source = tmp_path / "story.mp3"
    source.write_bytes(b"story")
    content = provider.import_content(source)
    content_directory = provider.media_root / content.id

    assert provider.delete(content.id) is True

    assert not content_directory.exists()
    assert repository.get_content(content.id) is None
    assert provider.delete(content.id) is False


def test_delete_refuses_path_outside_media_root(local_provider):
    provider, repository, tmp_path = local_provider
    outside = tmp_path / "do-not-delete"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep", encoding="utf-8")
    malicious = Content(
        title="Unsafe",
        provider="local",
        provider_reference="unsafe",
        local_path=str(outside),
    )
    repository.add_content(malicious)

    with pytest.raises(LocalContentError, match="escapes"):
        provider.delete(malicious.id)

    assert (outside / "keep.txt").read_text(encoding="utf-8") == "keep"
    assert repository.get_content(malicious.id) == malicious
