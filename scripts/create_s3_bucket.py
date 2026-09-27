#!/usr/bin/env python3
"""Create the transcript bucket on the configured S3-compatible endpoint."""

from __future__ import annotations

import os

import boto3
from botocore.config import Config


def main() -> None:
    bucket = os.getenv("S3_BUCKET", "youtube-transcripts")
    client = boto3.client(
        "s3",
        endpoint_url=os.getenv("S3_ENDPOINT", "http://localhost:9000"),
        aws_access_key_id=os.getenv("S3_ACCESS_KEY", "local"),
        aws_secret_access_key=os.getenv(
            "S3_SECRET_KEY", "local-dev-secret-change-me"
        ),
        region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
        config=Config(s3={"addressing_style": "path"}),
    )
    existing = {item["Name"] for item in client.list_buckets().get("Buckets", [])}
    if bucket not in existing:
        client.create_bucket(Bucket=bucket)
        print(f"Created S3 bucket {bucket}")
    else:
        print(f"S3 bucket {bucket} already exists")


if __name__ == "__main__":
    main()
