-- Canonical schema for the NameGnome cache database.
-- This mirrors migration 0001_initial.sql and is provided for reference / tooling.

CREATE TABLE IF NOT EXISTS kv (
    k TEXT PRIMARY KEY,
    v TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS entities (
    provider TEXT NOT NULL,
    type TEXT NOT NULL,
    ext_id TEXT NOT NULL,
    title_norm TEXT,
    title_raw TEXT,
    year INTEGER,
    metadata TEXT,
    fetched_at TEXT NOT NULL,
    ttl_seconds INTEGER DEFAULT 604800,
    PRIMARY KEY (provider, type, ext_id)
);

CREATE TABLE IF NOT EXISTS episodes (
    provider TEXT NOT NULL,
    series_id TEXT NOT NULL,
    season INTEGER NOT NULL,
    episode INTEGER NOT NULL,
    title TEXT,
    air_date TEXT,
    metadata TEXT,
    fetched_at TEXT NOT NULL,
    ttl_seconds INTEGER DEFAULT 604800,
    PRIMARY KEY (provider, series_id, season, episode)
);

CREATE TABLE IF NOT EXISTS tracks (
    provider TEXT NOT NULL,
    album_id TEXT NOT NULL,
    disc INTEGER DEFAULT 1,
    track INTEGER NOT NULL,
    title TEXT,
    metadata TEXT,
    fetched_at TEXT NOT NULL,
    ttl_seconds INTEGER DEFAULT 604800,
    PRIMARY KEY (provider, album_id, disc, track)
);

CREATE TABLE IF NOT EXISTS decisions (
    scope TEXT NOT NULL,
    title_norm TEXT NOT NULL,
    year INTEGER NOT NULL DEFAULT -1,
    provider TEXT NOT NULL,
    ext_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (scope, title_norm, year)
);

CREATE TABLE IF NOT EXISTS locks (
    name TEXT PRIMARY KEY,
    owner TEXT,
    acquired_at TEXT
);

CREATE TABLE IF NOT EXISTS cache_entries (
    cache_key TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    data TEXT NOT NULL,
    expires_at REAL NOT NULL,
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_entities_title_year
    ON entities (title_norm, year);

CREATE INDEX IF NOT EXISTS idx_episodes_series_season_ep
    ON episodes (series_id, season, episode);

CREATE INDEX IF NOT EXISTS idx_tracks_album_disc_track
    ON tracks (album_id, disc, track);

CREATE INDEX IF NOT EXISTS idx_cache_entries_provider
    ON cache_entries (provider);

CREATE INDEX IF NOT EXISTS idx_cache_entries_expires
    ON cache_entries (expires_at);
