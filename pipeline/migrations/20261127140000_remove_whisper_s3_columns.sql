-- migrate:up
ALTER TABLE phd_pipeline.whisper_transcript
    ALTER COLUMN drive_file_id SET NOT NULL,
    DROP COLUMN s3_bucket,
    DROP COLUMN bucket_key;

-- migrate:down
-- The previous S3 locations cannot be reconstructed for all Drive files.
ALTER TABLE phd_pipeline.whisper_transcript
    ADD COLUMN s3_bucket TEXT,
    ADD COLUMN bucket_key TEXT,
    ADD CONSTRAINT whisper_transcript_bucket_key_key UNIQUE (s3_bucket, bucket_key),
    ALTER COLUMN drive_file_id DROP NOT NULL;
