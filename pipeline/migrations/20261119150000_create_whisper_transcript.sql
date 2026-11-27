-- migrate:up
CREATE TABLE IF NOT EXISTS phd_pipeline.whisper_transcript (
    id                    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    video_id              bigint NOT NULL,
    file_format           varchar(50) NOT NULL DEFAULT 'txt',
    model_version         varchar(100) NOT NULL,
    acquired_at           timestamptz NOT NULL DEFAULT now(),
    transcription_seconds numeric(10,2),
    s3_bucket             text NOT NULL,
    bucket_key            text NOT NULL,
    size_bytes            bigint,
    CONSTRAINT whisper_transcript_video_id_key UNIQUE (video_id),
    CONSTRAINT whisper_transcript_bucket_key_key UNIQUE (s3_bucket, bucket_key),
    CONSTRAINT whisper_transcript_video_id_fkey FOREIGN KEY (video_id)
        REFERENCES phd_pipeline.video (id) ON DELETE RESTRICT,
    CONSTRAINT whisper_transcript_size_bytes_check
        CHECK (size_bytes IS NULL OR size_bytes >= 0)
);

-- migrate:down
DROP TABLE IF EXISTS phd_pipeline.whisper_transcript;
