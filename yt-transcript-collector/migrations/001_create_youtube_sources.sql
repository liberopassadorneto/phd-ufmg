CREATE TABLE IF NOT EXISTS youtube_sources (
    id BIGSERIAL PRIMARY KEY,
    video_id TEXT NOT NULL,
    youtube_url TEXT NOT NULL,
    title TEXT,
    channel_id TEXT,
    channel_name TEXT,
    published_at TEXT,
    duration_seconds INT,
    collected_at TEXT NOT NULL,
    s3_bucket TEXT NOT NULL,
    human_vtt_key TEXT,
    automatic_vtt_key TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS youtube_sources_video_id_idx
    ON youtube_sources (video_id);
