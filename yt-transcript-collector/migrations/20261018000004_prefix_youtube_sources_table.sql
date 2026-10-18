-- migrate:up
CREATE TABLE IF NOT EXISTS yt_transcript__youtube_sources (
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
    human_srt_key TEXT,
    automatic_srt_key TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS yt_transcript__youtube_sources_video_id_idx
    ON yt_transcript__youtube_sources (video_id);

INSERT INTO yt_transcript__youtube_sources (
    video_id,
    youtube_url,
    title,
    channel_id,
    channel_name,
    published_at,
    duration_seconds,
    collected_at,
    s3_bucket,
    human_srt_key,
    automatic_srt_key
)
SELECT
    video_id,
    youtube_url,
    title,
    channel_id,
    channel_name,
    published_at,
    duration_seconds,
    collected_at,
    s3_bucket,
    human_srt_key,
    automatic_srt_key
FROM youtube_sources
ON CONFLICT (video_id) DO NOTHING;

-- migrate:down
DROP TABLE IF EXISTS yt_transcript__youtube_sources;
