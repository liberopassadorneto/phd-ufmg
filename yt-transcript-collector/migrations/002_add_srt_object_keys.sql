ALTER TABLE youtube_sources
    ADD COLUMN IF NOT EXISTS human_srt_key TEXT,
    ADD COLUMN IF NOT EXISTS automatic_srt_key TEXT;
