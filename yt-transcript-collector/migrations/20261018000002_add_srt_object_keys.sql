-- migrate:up
ALTER TABLE youtube_sources
    ADD COLUMN IF NOT EXISTS human_srt_key TEXT,
    ADD COLUMN IF NOT EXISTS automatic_srt_key TEXT;

-- migrate:down
ALTER TABLE youtube_sources
    DROP COLUMN IF EXISTS human_srt_key,
    DROP COLUMN IF EXISTS automatic_srt_key;
