-- migrate:up
CREATE TABLE phd_pipeline.drive_file (
    -- A stable internal key keeps references independent of changes to paths.
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    drive_path TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT drive_file_path_not_blank CHECK (length(btrim(drive_path)) > 0)
);

ALTER TABLE phd_pipeline.whisper_transcript
    ADD COLUMN drive_file_id BIGINT UNIQUE
        REFERENCES phd_pipeline.drive_file(id) ON DELETE RESTRICT;

-- migrate:down
ALTER TABLE phd_pipeline.whisper_transcript DROP COLUMN drive_file_id;
DROP TABLE phd_pipeline.drive_file;
