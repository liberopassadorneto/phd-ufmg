#!/usr/bin/env python3
"""Initialize local SPG and S3 with the repository's reproducible sample."""

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
                print("SPG is ready")
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


def apply_migrations(conninfo: str) -> None:
    migrations = sorted((ROOT / "migrations").glob("*.sql"))
    with psycopg.connect(conninfo, connect_timeout=5) as conn:
        for migration in migrations:
            conn.execute(migration.read_text(encoding="utf-8"))
            print(f"Applied {migration.name}")


def ensure_sample_row(conninfo: str) -> None:
    columns = (
        "video_id, youtube_url, title, channel_id, channel_name, published_at, "
        "duration_seconds, collected_at, s3_bucket, automatic_srt_key"
    )
    values = tuple(SOURCE.values()) + (BUCKET, OBJECT_KEY)
    with psycopg.connect(conninfo, connect_timeout=5) as conn:
        existing = conn.execute(
            "SELECT id FROM youtube_sources WHERE video_id = %s",
            (VIDEO_ID,),
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE youtube_sources SET
                       youtube_url = %s, title = %s, channel_id = %s,
                       channel_name = %s, published_at = %s,
                       duration_seconds = %s, collected_at = %s,
                       s3_bucket = %s, human_srt_key = NULL,
                       automatic_srt_key = %s
                   WHERE video_id = %s""",
                (
                    SOURCE["youtube_url"], SOURCE["title"], SOURCE["channel_id"],
                    SOURCE["channel_name"], SOURCE["published_at"],
                    SOURCE["duration_seconds"], SOURCE["collected_at"], BUCKET,
                    OBJECT_KEY, VIDEO_ID,
                ),
            )
            print(f"Updated sample row for {VIDEO_ID}")
        else:
            placeholders = ", ".join(["%s"] * len(values))
            conn.execute(
                f"INSERT INTO youtube_sources ({columns}) VALUES ({placeholders})",
                values,
            )
            print(f"Inserted sample row for {VIDEO_ID}")


def main() -> None:
    conninfo = os.getenv(
        "DATABASE_URL", "host=postgres port=5432 dbname=postgres user=postgres"
    )
    client = s3_client()
    wait_for_database(conninfo)
    wait_for_s3(client)

    apply_migrations(conninfo)
    if BUCKET not in {
        bucket["Name"] for bucket in client.list_buckets().get("Buckets", [])
    }:
        client.create_bucket(Bucket=BUCKET)
        print(f"Created S3 bucket {BUCKET}")

    seed_file = ROOT / "seed_data" / VIDEO_ID / "automatic.srt"
    client.upload_file(
        str(seed_file), BUCKET, OBJECT_KEY,
        ExtraArgs={"ContentType": "text/plain; charset=utf-8"},
    )
    print(f"Seeded s3://{BUCKET}/{OBJECT_KEY}")
    ensure_sample_row(conninfo)


if __name__ == "__main__":
    main()
