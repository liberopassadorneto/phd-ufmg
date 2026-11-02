#!/usr/bin/env python3
"""Wait for shared services and ensure the pipeline transcript bucket exists."""

from __future__ import annotations

import os
import time
from typing import Any

import boto3
import psycopg
from botocore.config import Config


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
        endpoint_url=os.getenv("S3_ENDPOINT", "http://s3:9000"),
        aws_access_key_id=os.environ["S3_ACCESS_KEY"],
        aws_secret_access_key=os.environ["S3_SECRET_KEY"],
        region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
        config=Config(s3={"addressing_style": "path"}),
    )


def ensure_bucket(client: Any, bucket: str) -> None:
    for attempt in range(60):
        try:
            existing = {item["Name"] for item in client.list_buckets().get("Buckets", [])}
            if bucket not in existing:
                client.create_bucket(Bucket=bucket)
            print(f"S3 bucket {bucket} is ready")
            return
        except Exception:
            if attempt == 59:
                raise
            time.sleep(2)


def main() -> None:
    conninfo = os.environ["DATABASE_URL"]
    wait_for_database(conninfo)
    ensure_bucket(s3_client(), os.getenv("S3_BUCKET", "youtube-transcripts"))


if __name__ == "__main__":
    main()
