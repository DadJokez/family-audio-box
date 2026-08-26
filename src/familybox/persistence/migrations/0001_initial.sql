CREATE TABLE children (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    settings_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE devices (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    child_id TEXT REFERENCES children(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE content (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    content_type TEXT NOT NULL,
    provider TEXT NOT NULL,
    provider_reference TEXT NOT NULL,
    local_path TEXT,
    artwork_path TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX content_provider_idx ON content(provider);

CREATE TABLE content_tracks (
    id TEXT PRIMARY KEY,
    content_id TEXT NOT NULL REFERENCES content(id) ON DELETE CASCADE,
    track_index INTEGER NOT NULL CHECK (track_index >= 0),
    title TEXT NOT NULL,
    local_path TEXT,
    provider_reference TEXT,
    duration_seconds REAL CHECK (duration_seconds IS NULL OR duration_seconds >= 0),
    metadata_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE (content_id, track_index)
);

CREATE INDEX content_tracks_content_idx
    ON content_tracks(content_id, track_index);

CREATE TABLE tags (
    uid TEXT PRIMARY KEY,
    content_id TEXT NOT NULL REFERENCES content(id) ON DELETE CASCADE,
    name TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX tags_content_idx ON tags(content_id);

CREATE TABLE unknown_tags (
    uid TEXT PRIMARY KEY,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    detection_count INTEGER NOT NULL DEFAULT 1 CHECK (detection_count > 0)
);

CREATE INDEX unknown_tags_last_seen_idx ON unknown_tags(last_seen_at DESC);

CREATE TABLE playback_state (
    device_id TEXT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    content_id TEXT NOT NULL REFERENCES content(id) ON DELETE CASCADE,
    track_index INTEGER NOT NULL DEFAULT 0 CHECK (track_index >= 0),
    position_seconds REAL NOT NULL DEFAULT 0 CHECK (position_seconds >= 0),
    completed INTEGER NOT NULL DEFAULT 0 CHECK (completed IN (0, 1)),
    updated_at TEXT NOT NULL,
    PRIMARY KEY (device_id, content_id)
);

CREATE INDEX playback_state_updated_idx ON playback_state(updated_at);
