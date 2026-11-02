# UFMG Research Pipeline

The UFMG Research Pipeline collects YouTube videos related to research
queries and processes their transcripts to identify and classify claims. Its
database records the data and execution provenance produced by each stage.

## Project organization

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

## Shared PostgreSQL and S3

### Source of truth

Greenwich (`150.164.2.42`) hosts the shared PostgreSQL database and S3-compatible
object storage. PostgreSQL is the source of truth for structured records,
statuses, and workflow state. S3 stores transcript files; PostgreSQL records
their bucket and object key. Both hosts use these same services, so workers do
not synchronize separate database or file copies. The transcript bucket is
`youtube-transcripts`.

### Connect from Cuba

From a workstation, log in to Cuba through the bastion:

```bash
ssh -J libero_neto@150.164.2.44 libero_neto@150.164.2.13
```

On Cuba, open the tunnel to Greenwich in one terminal:

```bash
pipeline/bootstrap/open-shared-tunnel
```

The script connects as `marcele_araponga@150.164.2.42` and forwards PostgreSQL
port `15432` and S3 port `19000` to Cuba's localhost. Keep this terminal open
while workers use the services. If the SSH session closes or Cuba restarts,
run the command again. The root `.env` on Cuba must contain the shared database
and S3 credentials; keep it out of Git and set its permissions with
`chmod 600 .env`.

### Check the connection

In a second Cuba terminal, check the forwarded ports:

```bash
nc -vz -w 3 127.0.0.1 15432
nc -vz -w 3 127.0.0.1 19000
```

Then verify PostgreSQL authentication:

```bash
pipeline/bootstrap/with-shared-env bash -c \
  'psql "$DATABASE_URL" -c "select current_database(), current_user;"'
```

Verify S3 authentication and list the buckets:

```bash
pipeline/bootstrap/with-shared-env \
  uv run --frozen --project pipeline/step-3-transcript-acquisition \
  python -c 'import boto3, os; from botocore.config import Config; s=boto3.client("s3", endpoint_url=os.environ["S3_ENDPOINT"], aws_access_key_id=os.environ["S3_ACCESS_KEY"], aws_secret_access_key=os.environ["S3_SECRET_KEY"], region_name=os.environ["AWS_DEFAULT_REGION"], config=Config(s3={"addressing_style":"path"})); print([b["Name"] for b in s.list_buckets()["Buckets"]])'
```

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
