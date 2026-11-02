# UFMG Research Pipeline

The UFMG Research Pipeline collects YouTube videos related to research
queries and processes their transcripts to identify and classify claims. Its
database records the data and execution provenance produced by each stage.

## Contents

1. [Project Structure](#1-project-structure)
2. [Pipeline](#2-pipeline)
   - [Pipeline Steps](#pipeline-steps)
3. [Shared PostgreSQL and S3](#3-shared-postgresql-and-s3)
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

5. **Enable key-based SSH from Cuba to Greenwich.** The tunnel container uses
   `ssh-agent` and cannot answer an interactive password prompt. If needed,
   generate a key, authorize it on Greenwich, start the agent, and load the key:

   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_greenwich
   ssh-copy-id -i ~/.ssh/id_ed25519_greenwich.pub marcele_araponga@150.164.2.42
   eval "$(ssh-agent -s)"
   ssh-add ~/.ssh/id_ed25519_greenwich
   ```

   If a key is already authorized on Greenwich, load that key into the agent
   instead of generating another one.

6. **Start the tunnel with Docker Compose** on Cuba from the bootstrap directory:

   ```bash
   cd pipeline/bootstrap
   docker compose up -d --build
   ```

   This bootstrap Compose file starts only the SSH tunnel; `pipeline/compose.yaml`
   starts the shared PostgreSQL and S3 services on Greenwich. The tunnel connects
   as `marcele_araponga@150.164.2.42` and forwards those services to Cuba's
   localhost. To inspect or stop the tunnel, use:

   ```bash
   docker compose logs -f shared-tunnel
   docker compose down
   ```

   The container restarts with Docker while the SSH agent and loaded key are
   available. After a Cuba reboot, start the agent, load the key, then run
   `docker compose up -d` again.

7. **Check the tunnel on Cuba:**

   ```bash
   nc -vz -w 3 127.0.0.1 15432
   nc -vz -w 3 127.0.0.1 19000
   ```

8. **Verify database access from Cuba:**

   ```bash
   pipeline/bootstrap/with-shared-env bash -c \
     'psql "$DATABASE_URL" -c "select current_database(), current_user;"'
   ```

9. **Verify S3 access from Cuba** and list the available buckets:

   ```bash
   pipeline/bootstrap/with-shared-env \
     uv run --frozen --project pipeline/step-3-transcript-acquisition \
     python -c 'import boto3, os; from botocore.config import Config; s=boto3.client("s3", endpoint_url=os.environ["S3_ENDPOINT"], aws_access_key_id=os.environ["S3_ACCESS_KEY"], aws_secret_access_key=os.environ["S3_SECRET_KEY"], region_name=os.environ["AWS_DEFAULT_REGION"], config=Config(s3={"addressing_style":"path"})); print([b["Name"] for b in s.list_buckets()["Buckets"]])'
   ```

10. **Run workers through the shared environment wrapper.** Both hosts should
   use `pipeline/bootstrap/with-shared-env` so they connect to the same
   PostgreSQL database and S3 bucket.

### How data is shared

PostgreSQL is the source of truth for structured records, statuses, and
workflow state. S3 stores transcript files in the shared `youtube-transcripts`
bucket. Store each file's bucket and object key in PostgreSQL. Cuba and
Greenwich then read the same database records and S3 objects; do not maintain
or synchronize separate copies between the hosts.
