# YouTube Transcript Collector

This project downloads YouTube caption tracks as SRT, stores the raw files in
an S3-compatible bucket, and stores video metadata and S3 object keys in SPG.

## Start the local stack

From the repository root, run:

```bash
docker compose up --build -d
```

Compose starts SPG and local-s3, then runs a one-shot bootstrap service. The
bootstrap waits for both services, applies the SQL migrations, creates the
`youtube-transcripts` bucket, uploads the checked-in sample SRT, and inserts or
refreshes its matching `youtube_sources` row. It is safe to run again and does
not remove other rows or objects in existing volumes.

To see bootstrap progress:

```bash
docker compose logs bootstrap
```

The shared sample is video `xIUda-rBS-Q`. On a clean set of Docker volumes,
each developer gets the same sample row and the same SRT object:

- S3 object: `s3://youtube-transcripts/xIUda-rBS-Q/automatic.srt`
- PostgreSQL-compatible endpoint: `localhost:5432`
- S3 endpoint: `http://localhost:9000`

To inspect its database row:

```sql
SELECT id, video_id, youtube_url, title, s3_bucket, automatic_srt_key
FROM youtube_sources
WHERE video_id = 'xIUda-rBS-Q';
```

The named Docker volumes persist each developer's local data. The bootstrap
ensures the shared sample exists in each volume; it does not synchronize later
changes between developers or erase additional local data.
