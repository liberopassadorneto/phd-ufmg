ALTER TABLE youtube_sources
    DROP COLUMN IF EXISTS human_vtt_key,
    DROP COLUMN IF EXISTS automatic_vtt_key;
