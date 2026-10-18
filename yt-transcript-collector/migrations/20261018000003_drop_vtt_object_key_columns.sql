-- migrate:up
ALTER TABLE youtube_sources
    DROP COLUMN IF EXISTS human_vtt_key,
    DROP COLUMN IF EXISTS automatic_vtt_key;

-- migrate:down
ALTER TABLE youtube_sources
    ADD COLUMN IF NOT EXISTS human_vtt_key TEXT,
    ADD COLUMN IF NOT EXISTS automatic_vtt_key TEXT;
