-- migrate:up
ALTER TABLE phd_pipeline.transcript
    DROP CONSTRAINT IF EXISTS transcript_video_id_source_type_language_code_key,
    DROP COLUMN IF EXISTS source_type,
    DROP COLUMN IF EXISTS language_code,
    DROP COLUMN IF EXISTS acquisition_tool,
    ADD COLUMN IF NOT EXISTS transcription_seconds numeric(10,2),
    ADD CONSTRAINT transcript_video_id_key UNIQUE (video_id);

ALTER TABLE phd_pipeline.transcript
    RENAME COLUMN acquisition_tool_version TO model_version;

-- migrate:down
ALTER TABLE phd_pipeline.transcript
    RENAME COLUMN model_version TO acquisition_tool_version;

ALTER TABLE phd_pipeline.transcript
    DROP CONSTRAINT IF EXISTS transcript_video_id_key,
    DROP COLUMN IF EXISTS transcription_seconds,
    ADD COLUMN source_type phd_pipeline.transcript_source_enum,
    ADD COLUMN language_code varchar(20),
    ADD COLUMN acquisition_tool varchar(100) NOT NULL DEFAULT 'yt-dlp';
