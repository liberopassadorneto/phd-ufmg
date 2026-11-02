-- migrate:up
CREATE SCHEMA IF NOT EXISTS phd_pipeline;
SET search_path TO phd_pipeline, public;

-- ============================================================
-- PhD UFMG - PostgreSQL Schema
-- PK/FK/index strategy aligned with Snowflake Postgres guidance
--
-- Scientific pipeline:
-- 1. Query Definition
-- 2. YouTube Search + Metadata Collection
-- 3. Transcript Acquisition
-- 4. Content Eligibility Screening
-- 5. Claim Extraction
-- 6. Claim Classification
--
-- Key strategy:
-- - Internal entity PKs: BIGINT GENERATED ALWAYS AS IDENTITY
-- - External IDs (e.g. YouTube): regular columns with UNIQUE constraints
-- - Pure relationship tables: composite PKs when the relationship itself
--   is the natural identity
-- - Every FK is backed by a B-tree index, unless an existing PK/UNIQUE
--   index already covers that FK as its leftmost column
-- - SERIAL/BIGSERIAL intentionally not used
-- ============================================================


-- ------------------------------------------------------------
-- ENUMS
-- ------------------------------------------------------------

CREATE TYPE run_status_enum AS ENUM (
    'PENDING',
    'RUNNING',
    'SUCCEEDED',
    'FAILED'
);

CREATE TYPE transcript_source_enum AS ENUM (
    'YOUTUBE_MANUAL',
    'YOUTUBE_AUTOMATIC'
);

CREATE TYPE screening_decision_enum AS ENUM (
    'PASS',
    'FAIL',
    'UNCERTAIN'
);

CREATE TYPE screening_check_type_enum AS ENUM (
    'LANGUAGE',
    'TOPIC_RELEVANCE'
);

CREATE TYPE model_stage_enum AS ENUM (
    'CONTENT_SCREENING',
    'CLAIM_EXTRACTION',
    'CLAIM_CLASSIFICATION'
);

-- ------------------------------------------------------------
-- CROSS-CUTTING PROVENANCE
-- ------------------------------------------------------------

CREATE TABLE pipeline_run (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pipeline_version VARCHAR(50) NOT NULL,
    git_commit VARCHAR(64),
    configuration JSONB,
    status run_status_enum NOT NULL DEFAULT 'PENDING',
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE model_run (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pipeline_run_id BIGINT
        REFERENCES pipeline_run(id) ON DELETE RESTRICT,
    stage model_stage_enum NOT NULL,
    provider VARCHAR(100),
    model_name VARCHAR(255) NOT NULL,
    model_version VARCHAR(255),
    prompt_version VARCHAR(100),
    parameters JSONB,
    status run_status_enum NOT NULL DEFAULT 'PENDING',
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Covers FK model_run.pipeline_run_id because pipeline_run_id is the
-- leftmost column of the index, while also supporting stage filtering.
CREATE INDEX idx_model_run_pipeline_stage
    ON model_run (pipeline_run_id, stage);

-- ------------------------------------------------------------
-- 1. QUERY DEFINITION
-- ------------------------------------------------------------

CREATE TABLE search_query (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    query_text TEXT NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ------------------------------------------------------------
-- 2. YOUTUBE SEARCH + METADATA COLLECTION
-- ------------------------------------------------------------

CREATE TABLE search_run (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pipeline_run_id BIGINT
        REFERENCES pipeline_run(id) ON DELETE RESTRICT,
    query_id BIGINT NOT NULL
        REFERENCES search_query(id) ON DELETE RESTRICT,

    executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Search configuration used in the YouTube Data API request.
    order_by VARCHAR(50),
    region_code VARCHAR(10),
    relevance_language VARCHAR(20),
    published_after TIMESTAMPTZ,
    published_before TIMESTAMPTZ,
    max_results INTEGER CHECK (max_results IS NULL OR max_results > 0),
    additional_parameters JSONB,

    status run_status_enum NOT NULL DEFAULT 'PENDING',
    error_message TEXT
);

-- FK index for search_run.pipeline_run_id.
CREATE INDEX idx_search_run_pipeline
    ON search_run (pipeline_run_id);

-- Covers FK search_run.query_id and common query-history access pattern.
CREATE INDEX idx_search_run_query_executed
    ON search_run (query_id, executed_at DESC);

-- Internal synthetic PK; YouTube's ID is stored as an external identifier.
CREATE TABLE video (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    youtube_video_id TEXT NOT NULL UNIQUE,
    first_discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Relationship identity is naturally (search_run, video), so a composite
-- PK is appropriate here rather than adding an artificial row id.
CREATE TABLE search_result (
    search_run_id BIGINT NOT NULL
        REFERENCES search_run(id) ON DELETE CASCADE,
    video_id BIGINT NOT NULL
        REFERENCES video(id) ON DELETE RESTRICT,
    result_position INTEGER NOT NULL CHECK (result_position > 0),
    retrieved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (search_run_id, video_id),
    UNIQUE (search_run_id, result_position)
);

-- search_run_id is already indexed as the leftmost column of the PK.
-- video_id needs its own FK index.
CREATE INDEX idx_search_result_video
    ON search_result (video_id);

-- Metadata is snapshot-based because values may change over time.
CREATE TABLE video_metadata_snapshot (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    video_id BIGINT NOT NULL
        REFERENCES video(id) ON DELETE RESTRICT,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    youtube_channel_id TEXT,
    channel_title VARCHAR(255),
    published_at TIMESTAMPTZ,
    title TEXT,
    description TEXT,
    youtube_category_id TEXT,
    duration_seconds INTEGER
        CHECK (duration_seconds IS NULL OR duration_seconds >= 0),
    live_status VARCHAR(50),
    default_language VARCHAR(20),
    default_audio_language VARCHAR(20),

    view_count BIGINT
        CHECK (view_count IS NULL OR view_count >= 0),
    like_count BIGINT
        CHECK (like_count IS NULL OR like_count >= 0),
    comment_count BIGINT
        CHECK (comment_count IS NULL OR comment_count >= 0)
);

-- Covers FK video_metadata_snapshot.video_id and latest-snapshot access.
CREATE INDEX idx_video_metadata_snapshot_video_observed
    ON video_metadata_snapshot (video_id, observed_at DESC);

CREATE TABLE tag (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tag_text TEXT NOT NULL UNIQUE
);

-- Pure many-to-many relationship: composite PK is sufficient.
CREATE TABLE video_metadata_tag (
    metadata_snapshot_id BIGINT NOT NULL
        REFERENCES video_metadata_snapshot(id) ON DELETE CASCADE,
    tag_id BIGINT NOT NULL
        REFERENCES tag(id) ON DELETE RESTRICT,

    PRIMARY KEY (metadata_snapshot_id, tag_id)
);

-- metadata_snapshot_id is already indexed as the leftmost PK column.
-- tag_id needs an FK index for reverse lookups and parent deletes.
CREATE INDEX idx_video_metadata_tag_tag
    ON video_metadata_tag (tag_id);

-- ------------------------------------------------------------
-- 3. TRANSCRIPT ACQUISITION
-- ------------------------------------------------------------

CREATE TABLE transcript (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    video_id BIGINT NOT NULL
        REFERENCES video(id) ON DELETE RESTRICT,

    source_type transcript_source_enum NOT NULL,
    language_code VARCHAR(20) NOT NULL,
    file_format VARCHAR(20) NOT NULL,

    acquisition_tool VARCHAR(100) NOT NULL DEFAULT 'yt-dlp',
    acquisition_tool_version VARCHAR(100),
    acquired_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    s3_bucket TEXT NOT NULL,
    s3_key TEXT NOT NULL,
    size_bytes BIGINT
        CHECK (size_bytes IS NULL OR size_bytes >= 0),

    -- Logical deduplication across different queries/search runs.
    UNIQUE (video_id, source_type, language_code),

    -- Physical S3 location must also be unique.
    UNIQUE (s3_bucket, s3_key)
);

-- No extra index on transcript.video_id is needed: the UNIQUE index on
-- (video_id, source_type, language_code) already covers video_id as its
-- leftmost column.

-- ------------------------------------------------------------
-- 4. CONTENT ELIGIBILITY SCREENING
-- ------------------------------------------------------------

CREATE TABLE content_screening (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pipeline_run_id BIGINT
        REFERENCES pipeline_run(id) ON DELETE RESTRICT,
    transcript_id BIGINT NOT NULL
        REFERENCES transcript(id) ON DELETE RESTRICT,
    model_run_id BIGINT
        REFERENCES model_run(id) ON DELETE RESTRICT,

    screening_version VARCHAR(100) NOT NULL,
    decision screening_decision_enum NOT NULL,
    reason_code VARCHAR(100),
    reason TEXT,

    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_content_screening_pipeline
    ON content_screening (pipeline_run_id);

-- Covers FK transcript_id and common history-by-transcript queries.
CREATE INDEX idx_content_screening_transcript_created
    ON content_screening (transcript_id, created_at DESC);

CREATE INDEX idx_content_screening_model
    ON content_screening (model_run_id);

CREATE TABLE content_screening_check (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    screening_id BIGINT NOT NULL
        REFERENCES content_screening(id) ON DELETE CASCADE,
    check_type screening_check_type_enum NOT NULL,
    decision screening_decision_enum NOT NULL,
    score NUMERIC(8,6)
        CHECK (score IS NULL OR (score >= 0 AND score <= 1)),
    detected_value TEXT,
    reason_code VARCHAR(100),
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (screening_id, check_type)
);

-- No extra FK index on screening_id is needed: the UNIQUE index on
-- (screening_id, check_type) already covers it as the leftmost column.
-- Low-cardinality indexes on check_type/decision are intentionally omitted
-- until an actual query pattern justifies them.

-- ------------------------------------------------------------
-- 5. CLAIM EXTRACTION
-- ------------------------------------------------------------

CREATE TABLE claim_extraction_run (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pipeline_run_id BIGINT
        REFERENCES pipeline_run(id) ON DELETE RESTRICT,
    screening_id BIGINT NOT NULL
        REFERENCES content_screening(id) ON DELETE RESTRICT,
    model_run_id BIGINT NOT NULL
        REFERENCES model_run(id) ON DELETE RESTRICT,

    status run_status_enum NOT NULL DEFAULT 'PENDING',
    error_message TEXT,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_claim_extraction_pipeline
    ON claim_extraction_run (pipeline_run_id);

CREATE INDEX idx_claim_extraction_screening
    ON claim_extraction_run (screening_id);

CREATE INDEX idx_claim_extraction_model
    ON claim_extraction_run (model_run_id);

CREATE TABLE claim (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    claim_extraction_run_id BIGINT NOT NULL
        REFERENCES claim_extraction_run(id) ON DELETE RESTRICT,
    claim_index INTEGER NOT NULL CHECK (claim_index >= 0),
    claim_text TEXT NOT NULL,

    source_start_char INTEGER
        CHECK (source_start_char IS NULL OR source_start_char >= 0),
    source_end_char INTEGER
        CHECK (source_end_char IS NULL OR source_end_char >= 0),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (claim_extraction_run_id, claim_index),
    CHECK (
        source_start_char IS NULL
        OR source_end_char IS NULL
        OR source_end_char >= source_start_char
    )
);

-- No extra FK index on claim_extraction_run_id is needed: the UNIQUE index
-- on (claim_extraction_run_id, claim_index) already covers it.

-- ------------------------------------------------------------
-- 6. CLAIM CLASSIFICATION
-- ------------------------------------------------------------

CREATE TABLE claim_classification_run (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pipeline_run_id BIGINT
        REFERENCES pipeline_run(id) ON DELETE RESTRICT,
    model_run_id BIGINT NOT NULL
        REFERENCES model_run(id) ON DELETE RESTRICT,

    status run_status_enum NOT NULL DEFAULT 'PENDING',
    error_message TEXT,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_claim_classification_run_pipeline
    ON claim_classification_run (pipeline_run_id);

CREATE INDEX idx_claim_classification_run_model
    ON claim_classification_run (model_run_id);

CREATE TABLE claim_classification (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    claim_classification_run_id BIGINT NOT NULL
        REFERENCES claim_classification_run(id) ON DELETE RESTRICT,
    claim_id BIGINT NOT NULL
        REFERENCES claim(id) ON DELETE RESTRICT,

    label TEXT NOT NULL,
    confidence NUMERIC(8,6)
        CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    explanation TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (claim_classification_run_id, claim_id)
);

-- claim_classification_run_id is already indexed as the leftmost column of
-- the UNIQUE index. claim_id needs its own FK index.
CREATE INDEX idx_claim_classification_claim
    ON claim_classification (claim_id);


DROP TABLE IF EXISTS public.yt_transcript__youtube_sources CASCADE;
DROP TABLE IF EXISTS public.youtube_sources CASCADE;
DELETE FROM public.schema_migrations WHERE version IN ('20261018000001', '20261018000002', '20261018000003', '20261018000004');
