# UFMG Research Pipeline

The UFMG Research Pipeline collects YouTube videos related to research
queries and processes their transcripts to identify and classify claims. Its
database records the data and execution provenance produced by each stage.

## Contents

1. [Project Structure](#1-project-structure)
2. [Pipeline](#2-pipeline)
   - [Pipeline Steps](#pipeline-steps)
3. [Shared PostgreSQL and S3](#3-shared-postgresql-and-s3)
   - [TL;DR](#tldr)
   - [Architecture](#architecture)
   - [How to use it](#how-to-use-it)

## 1. Project Structure

Shared pipeline components live under `pipeline/`:

- `bootstrap/` contains shared-service initialization and connection helpers.
- `schema/` contains the final PostgreSQL schema definition.
- `migrations/` contains Dbmate migrations. `pipeline/compose.yaml` runs them
  when the Docker stack starts. Run it from the repository root with
  `docker compose --env-file .env -f pipeline/compose.yaml up -d`.
- `step-N-*` directories organize code by pipeline stage. Steps 1, 2, 4, 5,
  and 6 are TODO scaffolds; step 3 contains the transcript acquisition app.

The step 3 application downloads YouTube captions, stores the files in S3, and
updates only `phd_pipeline.transcript`. A video record must exist before a
transcript can be registered.

## 2. Pipeline

### Pipeline Steps

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

## 3. Shared PostgreSQL and S3

### TL;DR

- **Greenwich (`150.164.2.42`) hosts the shared services:** one PostgreSQL database and one S3-compatible `local-s3` store.
- **PostgreSQL is the source of truth for structured data** such as videos, transcript metadata, pipeline status, and claims.
- **S3 is the source of truth for file contents.** The shared transcript bucket is `youtube-transcripts`.
- **Cuba (`150.164.2.13`) and Greenwich use those same services.** Cuba reaches them through an SSH tunnel; there is no database or file synchronization between hosts.

### Architecture

```text
CUBA: workers                         GREENWICH: shared services
127.0.0.1:15432 ── SSH tunnel ──────► PostgreSQL (host :15432 → container :5432)
127.0.0.1:19000 ── SSH tunnel ──────► local-s3   (host :19000 → container :9000)
                                           │
                                     bucket: youtube-transcripts
```

A PostgreSQL record points to the file stored in S3:

```text
PostgreSQL row                         S3 object
bucket + object_key ─────────────────► youtube-transcripts/<object_key>
```

### How to use it

1. **Start PostgreSQL and `local-s3` on Greenwich** from the repository root:

   ```bash
   docker compose --env-file .env -f pipeline/compose.yaml up -d
   ```

2. **On Cuba, open the tunnel** from the repository root and keep it running while workers use the services:

   ```bash
   pipeline/bootstrap/open-shared-tunnel
   ```

   If the tunnel closes or Cuba restarts, run the command again. The project wrapper uses the forwarded localhost ports `15432` and `19000`.

3. **Check the tunnel from another Cuba terminal:**

   ```bash
   nc -vz -w 3 127.0.0.1 15432
   nc -vz -w 3 127.0.0.1 19000
   ```

4. **Run pipeline commands through the shared environment wrapper** on either host:

   ```bash
   pipeline/bootstrap/with-shared-env <command>
   ```

   The root `.env` on each host must contain credentials for the same shared database and S3 service. Keep it out of Git and set permissions with `chmod 600 .env`.

5. **When saving a file, upload it to S3 and store its bucket and object key in PostgreSQL.** After the database transaction commits, workers on the other host can query the record and read the same S3 object immediately.
