-- migrate:up
ALTER TABLE phd_pipeline.whisper_transcript
    ALTER COLUMN s3_bucket DROP NOT NULL,
    ALTER COLUMN bucket_key DROP NOT NULL;

-- migrate:down
-- Rollback requires restoring S3 locations for Drive-only records first.
ALTER TABLE phd_pipeline.whisper_transcript
    ALTER COLUMN s3_bucket SET NOT NULL,
    ALTER COLUMN bucket_key SET NOT NULL;
