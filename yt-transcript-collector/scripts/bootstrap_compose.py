#!/usr/bin/env python3
"""Initialize shared PostgreSQL and S3 with the repository's reproducible sample."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import boto3
import psycopg
from botocore.config import Config


ROOT = Path(__file__).resolve().parents[1]
VIDEO_ID = "xIUda-rBS-Q"
BUCKET = os.getenv("S3_BUCKET", "youtube-transcripts")
OBJECT_KEY = f"{VIDEO_ID}/automatic.srt"
SOURCE = {
    "video_id": VIDEO_ID,
    "youtube_url": "https://youtu.be/xIUda-rBS-Q?si=VT_5YERDobaFoG7M",
    "title": "O que você precisa saber sobre as “canetas emagrecedoras”",
    "channel_id": "UC9zqTTVeClpqMQ5CLuJdWtw",
    "channel_name": "Drauzio Varella",
    "published_at": "2026-03-16",
    "duration_seconds": 149,
    "collected_at": "2026-09-27T16:33:19-03:00",
}


def wait_for_database(conninfo: str) -> None:
    for attempt in range(60):
        try:
            with psycopg.connect(conninfo, connect_timeout=2):
                print("PostgreSQL is ready")
                return
        except psycopg.OperationalError:
            if attempt == 59:
                raise
            time.sleep(2)


def s3_client() -> Any:
    return boto3.client(
        "s3",
        endpoint_url=os.getenv("S3_ENDPOINT", "http://localhost:9000"),
        aws_access_key_id=os.getenv("S3_ACCESS_KEY", "local"),
        aws_secret_access_key=os.getenv(
            "S3_SECRET_KEY", "local-dev-secret-change-me"
        ),
        region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
        config=Config(s3={"addressing_style": "path"}),
    )


def wait_for_s3(client: Any) -> None:
    for attempt in range(60):
        try:
            client.list_buckets()
            print("Local S3 is ready")
            return
        except Exception:
            if attempt == 59:
                raise
            time.sleep(2)


def ensure_sample_row(conninfo: str) -> None:
    columns = (
        "video_id, youtube_url, title, channel_id, channel_name, published_at, "
        "duration_seconds, collected_at, s3_bucket, automatic_srt_key"
    )
    values = tuple(SOURCE.values()) + (BUCKET, OBJECT_KEY)
    with psycopg.connect(conninfo, connect_timeout=5) as conn:
        placeholders = ", ".join(["%s"] * len(values))
        conn.execute(
            f"""INSERT INTO yt_transcript__youtube_sources ({columns})
                VALUES ({placeholders})
                ON CONFLICT (video_id) DO UPDATE SET
                    youtube_url = EXCLUDED.youtube_url,
                    title = EXCLUDED.title,
                    channel_id = EXCLUDED.channel_id,
                    channel_name = EXCLUDED.channel_name,
                    published_at = EXCLUDED.published_at,
                    duration_seconds = EXCLUDED.duration_seconds,
                    collected_at = EXCLUDED.collected_at,
                    s3_bucket = EXCLUDED.s3_bucket,
                    human_srt_key = NULL,
                    automatic_srt_key = EXCLUDED.automatic_srt_key""",
            values,
        )
        print(f"Ensured sample row for {VIDEO_ID}")


def main() -> None:
    conninfo = os.getenv(
        "DATABASE_URL",
        "postgresql://phd_ufmg:phd_ufmg@postgres:5432/phd_ufmg?sslmode=disable",
    )
    client = s3_client()
    wait_for_database(conninfo)
    wait_for_s3(client)

    if BUCKET not in {
        bucket["Name"] for bucket in client.list_buckets().get("Buckets", [])
    }:
        try:
            client.create_bucket(Bucket=BUCKET)
            print(f"Created S3 bucket {BUCKET}")
        except Exception:
            buckets = {
                bucket["Name"] for bucket in client.list_buckets().get("Buckets", [])
            }
            if BUCKET not in buckets:
                raise

    seed_file = ROOT / "seed_data" / VIDEO_ID / "automatic.srt"
    client.upload_file(
        str(seed_file), BUCKET, OBJECT_KEY,
        ExtraArgs={"ContentType": "text/plain; charset=utf-8"},
    )
    print(f"Seeded s3://{BUCKET}/{OBJECT_KEY}")
    ensure_sample_row(conninfo)


if __name__ == "__main__":
    main()
