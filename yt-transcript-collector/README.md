# YouTube Transcript Collector

This project downloads YouTube caption tracks as SRT, stores the files in the
shared `youtube-transcripts` bucket, and stores metadata and object keys in the
`yt_transcript__youtube_sources` table in the shared PostgreSQL database.

The shared PostgreSQL, Dbmate, and S3 services are configured at the repository
root. Follow the root [README](../README.md) to create the server's shared `.env`
file and start the services. The first Compose startup applies migrations and
bootstraps the sample transcript. To apply new migrations later, run
`docker compose run --rm migrate` from the repository root.

Run the collector from an SSH session on the shared server:

```bash
./scripts/run-yt-transcript --url 'https://www.youtube.com/watch?v=VIDEO_ID'
```

The checked-in sample is video `xIUda-rBS-Q`; bootstrap stores its row and SRT
object in the shared database and bucket. To inspect the row:

```sql
SELECT id, video_id, youtube_url, title, s3_bucket, automatic_srt_key
FROM yt_transcript__youtube_sources
WHERE video_id = 'xIUda-rBS-Q';
```
