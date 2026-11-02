# Step 3: Transcript Acquisition

This project downloads YouTube caption tracks as SRT, stores the files in the
shared `youtube-transcripts` bucket, and inserts or updates only transcript
records in `phd_pipeline.transcript`. The corresponding video must already
exist in `phd_pipeline.video`; the collector resolves its external YouTube ID
(`youtube_video_id`) to the internal numeric `video.id`. Query and metadata
collection belong to the pipeline's earlier stages.

The shared PostgreSQL, Dbmate, and S3 services are configured by the root
Compose project. Follow the repository [README](../../README.md) to create the
shared `.env` file and start the services. The root pipeline bootstrap checks
the database connection and ensures the transcript bucket exists. To apply new
migrations later, run
`docker compose --env-file .env -f pipeline/compose.yaml run --rm migrate`
from the repository root.

From the repository root on the shared server, run:

```bash
./pipeline/step-3-transcript-acquisition/scripts/run-yt-transcript \
  --url 'https://www.youtube.com/watch?v=VIDEO_ID'
```

To inspect transcript records:

```sql
SELECT v.youtube_video_id, t.source_type, t.language_code, t.file_format,
       t.s3_bucket, t.s3_key, t.acquired_at
FROM phd_pipeline.transcript t
JOIN phd_pipeline.video v ON v.id = t.video_id
WHERE v.youtube_video_id = 'VIDEO_ID';
```
