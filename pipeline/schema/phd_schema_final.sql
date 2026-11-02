-- ============================================================
-- PhD UFMG - Final PostgreSQL Schema
--
-- Scientific pipeline:
-- 1. Query Definition
-- 2. YouTube Search + Metadata Collection
-- 3. Transcript Acquisition
-- 4. Content Eligibility Screening
-- 5. Claim Extraction
-- 6. Claim Classification
--
-- Experimental TODO (not modeled in the main flow):
-- YouTube Transcript vs Whisper Transcript
--
-- IMPORTANT:
-- Pipeline sequencing and branching are application/business rules.
-- Examples NOT enforced by the database:
--   - LANGUAGE is evaluated before TOPIC_RELEVANCE
--   - language != pt-BR stops screening
--   - only screening PASS continues to Claim Extraction
-- ============================================================

BEGIN;

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
    pipeline_run_id BIGSERIAL PRIMARY KEY,
    pipeline_version VARCHAR(50) NOT NULL,
    git_commit VARCHAR(64),
    configuration JSONB,
    status run_status_enum NOT NULL DEFAULT 'PENDING',
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE model_run (
    model_run_id BIGSERIAL PRIMARY KEY,
    pipeline_run_id BIGINT
        REFERENCES pipeline_run(pipeline_run_id) ON DELETE RESTRICT,
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

CREATE INDEX idx_model_run_pipeline_stage
    ON model_run (pipeline_run_id, stage);

-- ------------------------------------------------------------
-- 1. QUERY DEFINITION
-- ------------------------------------------------------------

CREATE TABLE search_query (
    query_id BIGSERIAL PRIMARY KEY,
    query_text TEXT NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ------------------------------------------------------------
-- 2. YOUTUBE SEARCH + METADATA COLLECTION
-- ------------------------------------------------------------

CREATE TABLE search_run (
    search_run_id BIGSERIAL PRIMARY KEY,
    pipeline_run_id BIGINT
        REFERENCES pipeline_run(pipeline_run_id) ON DELETE RESTRICT,
    query_id BIGINT NOT NULL
        REFERENCES search_query(query_id) ON DELETE RESTRICT,

    executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Search configuration used in the YouTube Data API request.
    -- Raw API responses are intentionally not stored.
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

CREATE INDEX idx_search_run_query
    ON search_run (query_id, executed_at DESC);

-- One YouTube video exists only once globally, regardless of how many
-- queries/search runs return it. The same video_id is reused everywhere.
CREATE TABLE video (
    video_id TEXT PRIMARY KEY,
    first_discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Represents which videos were returned by each query execution.
-- PRIMARY KEY (search_run_id, video_id) prevents duplicate occurrences of
-- the same video inside one search run while still allowing the same video
-- to appear in different queries/runs.
CREATE TABLE search_result (
    search_run_id BIGINT NOT NULL
        REFERENCES search_run(search_run_id) ON DELETE CASCADE,
    video_id TEXT NOT NULL
        REFERENCES video(video_id) ON DELETE RESTRICT,
    result_position INTEGER NOT NULL CHECK (result_position > 0),
    retrieved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (search_run_id, video_id),
    UNIQUE (search_run_id, result_position)
);

CREATE INDEX idx_search_result_video
    ON search_result (video_id);

-- Metadata is snapshot-based because values such as title, description,
-- tags and statistics may change if the same video is observed again.
CREATE TABLE video_metadata_snapshot (
    metadata_snapshot_id BIGSERIAL PRIMARY KEY,
    video_id TEXT NOT NULL
        REFERENCES video(video_id) ON DELETE RESTRICT,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    channel_id VARCHAR(255),
    channel_title VARCHAR(255),
    published_at TIMESTAMPTZ,
    title TEXT,
    description TEXT,
    category_id VARCHAR(50),
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

CREATE INDEX idx_video_metadata_snapshot_video
    ON video_metadata_snapshot (video_id, observed_at DESC);

CREATE TABLE tag (
    tag_id BIGSERIAL PRIMARY KEY,
    tag_text TEXT NOT NULL UNIQUE
);

CREATE TABLE video_metadata_tag (
    metadata_snapshot_id BIGINT NOT NULL
        REFERENCES video_metadata_snapshot(metadata_snapshot_id) ON DELETE CASCADE,
    tag_id BIGINT NOT NULL
        REFERENCES tag(tag_id) ON DELETE RESTRICT,

    PRIMARY KEY (metadata_snapshot_id, tag_id)
);

-- ------------------------------------------------------------
-- 3. TRANSCRIPT ACQUISITION
-- ------------------------------------------------------------

-- Only the caption/transcript file actually used is persisted in S3.
-- The schema intentionally does NOT store:
--   - raw YouTube API JSON
--   - video/audio files
--   - multiple derived TXT/SRT/JSON copies of the same transcript
--   - SHA/checksum calculated by the pipeline
CREATE TABLE transcript (
    transcript_id BIGSERIAL PRIMARY KEY,
    video_id TEXT NOT NULL
        REFERENCES video(video_id) ON DELETE RESTRICT,

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

    -- Prevents downloading/registering the same YouTube transcript again
    -- when the same video appears in other queries or search runs.
    UNIQUE (video_id, source_type, language_code),

    -- Physical S3 location must also be unique.
    UNIQUE (s3_bucket, s3_key)
);

-- ------------------------------------------------------------
-- 4. CONTENT ELIGIBILITY SCREENING
-- ------------------------------------------------------------

-- The database records the screening outcome.
-- Execution order and short-circuit rules belong to the application.
CREATE TABLE content_screening (
    screening_id BIGSERIAL PRIMARY KEY,
    pipeline_run_id BIGINT
        REFERENCES pipeline_run(pipeline_run_id) ON DELETE RESTRICT,
    transcript_id BIGINT NOT NULL
        REFERENCES transcript(transcript_id) ON DELETE RESTRICT,
    model_run_id BIGINT
        REFERENCES model_run(model_run_id) ON DELETE RESTRICT,

    screening_version VARCHAR(100) NOT NULL,
    decision screening_decision_enum NOT NULL,
    reason_code VARCHAR(100),
    reason TEXT,

    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_content_screening_transcript
    ON content_screening (transcript_id, created_at DESC);

CREATE INDEX idx_content_screening_decision
    ON content_screening (decision);

-- Detailed checks performed inside one Content Eligibility Screening run.
-- LANGUAGE and TOPIC_RELEVANCE are persisted independently when executed.
CREATE TABLE content_screening_check (
    screening_check_id BIGSERIAL PRIMARY KEY,
    screening_id BIGINT NOT NULL
        REFERENCES content_screening(screening_id) ON DELETE CASCADE,
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

CREATE INDEX idx_screening_check_type_decision
    ON content_screening_check (check_type, decision);

-- ------------------------------------------------------------
-- 5. CLAIM EXTRACTION
-- ------------------------------------------------------------

-- The application decides which screening records are allowed to reach
-- this stage (normally only PASS). The database does not enforce that rule.
CREATE TABLE claim_extraction_run (
    claim_extraction_run_id BIGSERIAL PRIMARY KEY,
    pipeline_run_id BIGINT
        REFERENCES pipeline_run(pipeline_run_id) ON DELETE RESTRICT,
    screening_id BIGINT NOT NULL
        REFERENCES content_screening(screening_id) ON DELETE RESTRICT,
    model_run_id BIGINT NOT NULL
        REFERENCES model_run(model_run_id) ON DELETE RESTRICT,

    status run_status_enum NOT NULL DEFAULT 'PENDING',
    error_message TEXT,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_claim_extraction_screening
    ON claim_extraction_run (screening_id);

CREATE TABLE claim (
    claim_id BIGSERIAL PRIMARY KEY,
    claim_extraction_run_id BIGINT NOT NULL
        REFERENCES claim_extraction_run(claim_extraction_run_id) ON DELETE RESTRICT,
    claim_index INTEGER NOT NULL CHECK (claim_index >= 0),
    claim_text TEXT NOT NULL,

    -- Optional traceability to the source transcript text.
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

CREATE INDEX idx_claim_extraction_run
    ON claim (claim_extraction_run_id);

-- ------------------------------------------------------------
-- 6. CLAIM CLASSIFICATION
-- ------------------------------------------------------------

CREATE TABLE claim_classification_run (
    claim_classification_run_id BIGSERIAL PRIMARY KEY,
    pipeline_run_id BIGINT
        REFERENCES pipeline_run(pipeline_run_id) ON DELETE RESTRICT,
    model_run_id BIGINT NOT NULL
        REFERENCES model_run(model_run_id) ON DELETE RESTRICT,

    status run_status_enum NOT NULL DEFAULT 'PENDING',
    error_message TEXT,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE claim_classification (
    classification_id BIGSERIAL PRIMARY KEY,
    claim_classification_run_id BIGINT NOT NULL
        REFERENCES claim_classification_run(claim_classification_run_id) ON DELETE RESTRICT,
    claim_id BIGINT NOT NULL
        REFERENCES claim(claim_id) ON DELETE RESTRICT,

    -- TEXT until the final PhD classification taxonomy is frozen.
    label TEXT NOT NULL,
    confidence NUMERIC(8,6)
        CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    explanation TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (claim_classification_run_id, claim_id)
);

CREATE INDEX idx_claim_classification_claim
    ON claim_classification (claim_id);

COMMIT;
