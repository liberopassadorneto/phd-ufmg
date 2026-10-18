#!/usr/bin/env python3
"""Create a project bucket in the shared S3-compatible service if needed."""

from __future__ import annotations

import argparse
import os

import boto3
from botocore.config import Config


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bucket", help="project-specific bucket name")
    args = parser.parse_args()

    client = boto3.client(
        "s3",
        endpoint_url=os.getenv("S3_ENDPOINT", "http://127.0.0.1:9000"),
        aws_access_key_id=os.getenv("S3_ACCESS_KEY"),
        aws_secret_access_key=os.getenv("S3_SECRET_KEY"),
        region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
        config=Config(s3={"addressing_style": "path"}),
    )
    existing = {item["Name"] for item in client.list_buckets().get("Buckets", [])}
    if args.bucket in existing:
        print(f"S3 bucket {args.bucket} already exists")
        return
    client.create_bucket(Bucket=args.bucket)
    print(f"Created S3 bucket {args.bucket}")


if __name__ == "__main__":
    main()
