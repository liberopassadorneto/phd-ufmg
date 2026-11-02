# UFMG Research Pipeline

The UFMG Research Pipeline collects YouTube videos related to research
queries and processes their transcripts to identify and classify claims. Its
database records the data and execution provenance produced by each stage.

## Contents

1. [Project Structure](#1-project-structure)
2. [Pipeline](#2-pipeline)
   - [Pipeline Steps](#pipeline-steps)
3. [Shared PostgreSQL and S3](#3-shared-postgresql-and-s3)
   - [Architecture overview](#architecture-overview)
   - [PostgreSQL: structured data](#postgresql-structured-data)
   - [S3-compatible storage: files](#s3-compatible-storage-files)
   - [End-to-end data flow](#end-to-end-data-flow)
   - [Step-by-step use](#step-by-step-use)
   - [How data is shared](#how-data-is-shared)

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

### Architecture overview

Greenwich (`150.164.2.42`) hosts the one shared PostgreSQL database and the
project's S3-compatible object store (`local-s3`). Cuba (`150.164.2.13`) reaches
both through one SSH tunnel. The services bind to Greenwich's loopback ports;
the tunnel makes them available on Cuba's loopback without exposing their ports
directly to the network.

```text
                          SHARED SOURCE OF TRUTH

  cuba (150.164.2.13)                         greenwich (150.164.2.42)
  ┌────────────────────┐                     ┌──────────────────────────┐
  │ pipeline / workers │                     │ 127.0.0.1:15432           │
  │                    │                     │       │                  │
  │ localhost:15432 ───┼──── SSH tunnel ────►│       └─► PostgreSQL :5432│
  │ localhost:19000 ───┼──── SSH tunnel ────►│                          │
  └────────────────────┘                     │ 127.0.0.1:19000           │
                                              │       └─► local-s3 :9000 │
                                              └──────────────────────────┘
```

### PostgreSQL: structured data

PostgreSQL is the single source of truth for structured records, pipeline
status, relationships, and provenance. Both hosts read and write the same
database; there is no separate Cuba database to synchronize.

```text
cuba worker ── localhost:15432 ── SSH ──┐
                                         ├── one PostgreSQL database
Greenwich worker ── localhost:15432 ────┘
```

An insert or update committed by either host is immediately visible to queries
from the other host.

### S3-compatible storage: files

The project currently runs `local-s3`, an S3-compatible service, on Greenwich.
Its host port is `19000` and its container API port is `9000`. The shared
transcript bucket is `youtube-transcripts`. This is the project's current
object store; it is not an AWS S3 bucket or a MinIO deployment.

PostgreSQL stores the reference to each file, while S3 stores the file bytes:

```text
PostgreSQL record                         S3 object
┌─────────────────────────────┐           ┌──────────────────────────────┐
│ transcript metadata         │           │ bucket: youtube-transcripts  │
│ bucket: youtube-transcripts ├──────────►│ key: transcripts/<video>/...│
│ object key: transcripts/... │           │ file bytes                   │
└─────────────────────────────┘           └──────────────────────────────┘
```

Workers on both hosts use the same bucket and object keys. Use unique or
deterministic object keys so concurrent workers do not overwrite unrelated
files.

### End-to-end data flow

For example, when a Cuba worker acquires a transcript:

```text
1. Cuba worker downloads transcript
2. PUT file to S3: youtube-transcripts/transcripts/<video-id>/transcript.txt
3. INSERT transcript metadata and object key into PostgreSQL
4. COMMIT
5. Greenwich reads the PostgreSQL row and GETs the same S3 object
```

Upload the object before committing its database reference. Once the commit
succeeds, Greenwich can discover the row and fetch the object immediately.
There is no database replication, file copy, `rsync`, or synchronization job
between Cuba and Greenwich.

### Step-by-step use

Greenwich (`150.164.2.42`) hosts the single shared PostgreSQL database and the
S3-compatible object store. Follow these steps to use them from either host.

1. **Start the shared services on Greenwich.** From the repository root on
   Greenwich, run this once or whenever the services are stopped:

   ```bash
   docker compose --env-file .env -f pipeline/compose.yaml up -d
   ```

2. **Configure the credentials on both hosts.** The root `.env` on Greenwich
   and Cuba must provide the credentials for the same database and S3 store.
   Keep `.env` out of Git and restrict access with `chmod 600 .env`.

3. **Use the services locally from Greenwich.** Run database and pipeline
   commands through `pipeline/bootstrap/with-shared-env`. It sets the database
   URL to `127.0.0.1:15432` and the S3 endpoint to `127.0.0.1:19000`.

4. **Log in to Cuba from your workstation** through the bastion:

   ```bash
   ssh -J libero_neto@150.164.2.44 libero_neto@150.164.2.13
   ```

5. **Open the tunnel from Cuba to Greenwich.** In a Cuba terminal, run:

   ```bash
   pipeline/bootstrap/open-shared-tunnel
   ```

   The script connects as `marcele_araponga@150.164.2.42` and forwards the
   shared PostgreSQL and S3 ports to Cuba's localhost. Keep this terminal open
   while workers use the services. If the SSH session closes or Cuba restarts,
   open the tunnel again.

6. **Check the tunnel from a second Cuba terminal:**

   ```bash
   nc -vz -w 3 127.0.0.1 15432
   nc -vz -w 3 127.0.0.1 19000
   ```

7. **Verify database access from Cuba:**

   ```bash
   pipeline/bootstrap/with-shared-env bash -c \
     'psql "$DATABASE_URL" -c "select current_database(), current_user;"'
   ```

8. **Verify S3 access from Cuba** and list the available buckets:

   ```bash
   pipeline/bootstrap/with-shared-env \
     uv run --frozen --project pipeline/step-3-transcript-acquisition \
     python -c 'import boto3, os; from botocore.config import Config; s=boto3.client("s3", endpoint_url=os.environ["S3_ENDPOINT"], aws_access_key_id=os.environ["S3_ACCESS_KEY"], aws_secret_access_key=os.environ["S3_SECRET_KEY"], region_name=os.environ["AWS_DEFAULT_REGION"], config=Config(s3={"addressing_style":"path"})); print([b["Name"] for b in s.list_buckets()["Buckets"]])'
   ```

9. **Run workers through the shared environment wrapper.** Both hosts should
   use `pipeline/bootstrap/with-shared-env` so they connect to the same
   PostgreSQL database and S3 bucket.

### How data is shared

PostgreSQL is the source of truth for structured records, statuses, and
workflow state. S3 stores transcript files in the shared `youtube-transcripts`
bucket. Store each file's bucket and object key in PostgreSQL. Cuba and
Greenwich then read the same database records and S3 objects; do not maintain
or synchronize separate copies between the hosts.
