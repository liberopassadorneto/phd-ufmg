# UFMG Research Pipeline

The UFMG Research Pipeline collects YouTube videos related to research
queries and processes their transcripts to identify and classify claims. Its
database records the data and execution provenance produced by each stage.

## Project organization

Shared pipeline components live under `pipeline/`:

- `bootstrap/` contains shared-service initialization and connection helpers.
- `schema/` contains the final PostgreSQL schema definition.
- `migrations/` contains Dbmate migrations. The root `compose.yaml` runs them
  when the Docker stack starts.
- `step-N-*` directories organize code by pipeline stage. Steps 1, 2, 4, 5,
  and 6 are TODO scaffolds; step 3 contains the transcript acquisition app.

The step 3 application downloads YouTube captions, stores the files in S3, and
updates only `phd_pipeline.transcript`. A video record must exist before a
transcript can be registered.

## Pipeline steps

1. **Query Definition** — Define the queries used to find relevant YouTube
   videos.
2. **YouTube Search and Metadata Collection** — Search YouTube with those
   queries, record the results, and collect video metadata.
3. **Transcript Acquisition** — Download available YouTube caption tracks and
   store transcript files and their records. The
   `pipeline/step-3-transcript-acquisition` project handles this stage; videos
   must already be registered by the earlier stages.
4. **Content Eligibility Screening** — Evaluate transcript language and topic
   relevance to decide whether the content can proceed.
5. **Claim Extraction** — Extract claims from eligible transcripts, retaining
   source positions when available. Only content that passes screening
   proceeds to this stage.
6. **Claim Classification** — Assign classifications to extracted claims.

The database schema represents all six steps. Applications control their
execution order and branching, including the rule that only transcripts that
pass screening proceed to claim extraction.
