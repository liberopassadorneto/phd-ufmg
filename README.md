# Shared PostgreSQL and S3 for `phd-ufmg`

Every project in this repository, including the YouTube Transcript Collector,
must use the shared PostgreSQL and S3 services owned by the root Compose
project. Do not create a separate PostgreSQL or S3 container for an individual
project. This gives developers working over SSH on this server the same database
and object data.

The stack runs PostgreSQL 18 (`postgres:18-alpine`), Dbmate for SQL migrations,
and S3-compatible storage (`ghcr.io/shyim/local-s3:latest`). PostgreSQL uses the
`phd_ufmg` database. New projects should keep tables in a project-specific
PostgreSQL schema and objects in a project-specific S3 bucket. The YT Collector
currently retains its existing prefixed table,
`yt_transcript__youtube_sources`, and uses the `youtube-transcripts` bucket.

## One-time setup on the server

An administrator sets up the shared environment file once at the repository
root:

```bash
cp .env.example .env
```

Set `POSTGRES_PASSWORD` and `S3_SECRET_KEY` to separate random hex values (for
example, generate each with `openssl rand -hex 24`). Keep `.env` out of Git and
grant read access only to the server users who need the services. The services
bind to loopback ports `15432` (PostgreSQL) and `19000` (S3) by default.

Initialize and start the stack from the repository root:

```bash
docker compose up --build -d
docker compose logs migrate yt-bootstrap
```

On the first start, Docker creates the named data volumes, PostgreSQL creates
the `phd_ufmg` database, Dbmate applies the registered migrations, and the YT
Collector bootstrap creates `youtube-transcripts` and stores its checked-in
sample transcript. This initialization is shared; developers should not set up
separate database or S3 instances.

## How developers share data

Each developer connects to these same services using the server's system Docker
daemon, the root Compose project, and the shared `.env` file. Use the repository
root Compose project; do not pass `-p` or set `COMPOSE_PROJECT_NAME`. Host-run
applications can load the connection variables with
`scripts/with-shared-env`:

```bash
./scripts/with-shared-env command arg1 arg2
```

For example, run the YT Collector from an SSH session:

```bash
./scripts/run-yt-transcript --url 'https://www.youtube.com/watch?v=VIDEO_ID'
```

If a developer needs to start services that are stopped, run `docker compose up
-d` from the same root project. Compose reuses the existing named volumes; it
does not create a fresh database for each developer. A record or S3 object added
by developer A is available to developer B when B connects to the same database
or bucket. Developers running applications in containers on the root Compose
network use `postgres:5432` and `http://s3:9000`. A separate application Compose
file must join the external network `phd-ufmg_default`.

The application containers and volumes must be on this server's system Docker
daemon. Running Compose on a laptop or through a separate rootless Docker daemon
would use different containers and data. `local-s3` stores objects on the
mounted filesystem at `/data`; back up the S3 volume if its contents matter.

## Add a project

Every project that needs persistent relational or object data must use these
shared services. Register a project migration directory in the root
`compose.yaml` under the `migrate` service by adding another `--migrations-dir`
and its path under `/workspace`. For example, the command can include both:

```yaml
command:
  - --migrations-dir
  - /workspace/yt-transcript-collector/migrations
  - --migrations-dir
  - /workspace/my-project/migrations
  - migrate
```

Create the project migration directory and generate versioned SQL migrations
with Dbmate:

```bash
mkdir -p my-project/migrations
docker compose run --rm migrate \
  --migrations-dir /workspace/my-project/migrations \
  new create_results
```

Use a project-specific PostgreSQL schema in the first migration, then put that
project's tables in it:

```sql
-- migrate:up
CREATE SCHEMA IF NOT EXISTS my_project;
CREATE TABLE my_project.results (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    payload JSONB NOT NULL
);

-- migrate:down
DROP TABLE IF EXISTS my_project.results;
DROP SCHEMA IF EXISTS my_project;
```

All registered directories share Dbmate's `schema_migrations` table in the
shared database. Migration versions must be globally unique across projects;
never edit a migration after it has been applied. Use the `migrate:up` and
`migrate:down` sections. To apply pending migrations, run this from the
repository root:

```bash
docker compose run --rm migrate
```

Only one developer should apply migrations at a time. Once applied, a migration
changes the shared database for every developer. New migration files must be
available in the shared repository checkout before they are applied.

Each project should use its own bucket in the shared S3 service. Host-run
applications receive common connection settings from `scripts/with-shared-env`;
set `S3_BUCKET` for the project. For example:

```bash
S3_BUCKET=my-project ./scripts/with-shared-env \
  uv run --project my-project python app.py

S3_BUCKET=my-project ./scripts/with-shared-env \
  uv run --project yt-transcript-collector \
  python scripts/create_s3_bucket.py my-project
```

Keep bucket names and credentials out of source control. New projects should
document their shared-service connection in their own README and must not
introduce another PostgreSQL or S3 Compose stack.

## Data persistence and lifecycle

The root Compose project uses the named volumes `phd-ufmg_postgres-data` and
`phd-ufmg_s3-data`. They persist on this server when containers stop or are
recreated. `docker compose down` stops and removes the containers and network
but preserves both volumes. **Do not run `docker compose down -v`** unless you
intend to permanently delete the shared database and S3 objects. Back up both
volumes before planned maintenance.

This stack starts with fresh volumes. Any previous YT Collector SPG or S3
volumes are left untouched and are not mounted by the root Compose project.
