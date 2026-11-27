-- migrate:up
-- 1. Amplia file_format para suportar todas as modalidades combinadas
ALTER TABLE phd_pipeline.transcript
ALTER COLUMN file_format TYPE VARCHAR(50);

-- 2. Remove eventuais duplicatas por (video_id, s3_bucket), priorizando YOUTUBE_MANUAL
DELETE FROM phd_pipeline.transcript a
USING phd_pipeline.transcript b
WHERE a.video_id = b.video_id
  AND a.s3_bucket = b.s3_bucket
  AND a.id <> b.id
  AND (
	      (b.source_type = 'YOUTUBE_MANUAL' AND a.source_type <> 'YOUTUBE_MANUAL')
	      OR (a.source_type = b.source_type AND a.id > b.id)
	  );

	-- 3. Normaliza s3_key para 'data/<youtube_video_id>'
UPDATE phd_pipeline.transcript t
SET s3_key = 'data/' || v.youtube_video_id
FROM phd_pipeline.video v
WHERE t.video_id = v.id
  AND t.s3_key <> ('data/' || v.youtube_video_id);

-- 4. Renomeia a coluna e o índice único para bucket_key
ALTER INDEX IF EXISTS transcript_s3_bucket_s3_key_key
RENAME TO transcript_s3_bucket_bucket_key_key;

ALTER TABLE phd_pipeline.transcript
RENAME COLUMN s3_key TO bucket_key;

-- migrate:down
ALTER TABLE phd_pipeline.transcript
RENAME COLUMN bucket_key TO s3_key;

ALTER INDEX IF EXISTS transcript_s3_bucket_bucket_key_key
RENAME TO transcript_s3_bucket_s3_key_key;

ALTER TABLE phd_pipeline.transcript
ALTER COLUMN file_format TYPE VARCHAR(20);

