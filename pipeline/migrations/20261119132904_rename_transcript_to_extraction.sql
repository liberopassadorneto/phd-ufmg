-- migrate:up
ALTER TABLE phd_pipeline.transcript
RENAME TO extraction;

ALTER TABLE phd_pipeline.extraction
RENAME CONSTRAINT transcript_pkey TO extraction_pkey;

ALTER TABLE phd_pipeline.extraction
RENAME CONSTRAINT transcript_s3_bucket_s3_key_key TO extraction_s3_bucket_bucket_key_key;

ALTER TABLE phd_pipeline.extraction
RENAME CONSTRAINT transcript_size_bytes_check TO extraction_size_bytes_check;

ALTER TABLE phd_pipeline.extraction
RENAME CONSTRAINT transcript_video_id_fkey TO extraction_video_id_fkey;

-- migrate:down
ALTER TABLE phd_pipeline.extraction
RENAME CONSTRAINT extraction_video_id_fkey TO transcript_video_id_fkey;

ALTER TABLE phd_pipeline.extraction
RENAME CONSTRAINT extraction_size_bytes_check TO transcript_size_bytes_check;

ALTER TABLE phd_pipeline.extraction
RENAME CONSTRAINT extraction_s3_bucket_bucket_key_key TO transcript_s3_bucket_s3_key_key;

ALTER TABLE phd_pipeline.extraction
RENAME CONSTRAINT extraction_pkey TO transcript_pkey;

ALTER TABLE phd_pipeline.extraction
RENAME TO transcript;
