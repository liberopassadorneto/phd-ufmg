#!/usr/bin/env python3
"""Check connectivity to the shared PostgreSQL and S3 services."""

from __future__ import annotations

import os
import sys


def test_postgres() -> bool:
    try:
        import psycopg

        conninfo = os.getenv("DATABASE_URL")
        if not conninfo:
            raise RuntimeError("DATABASE_URL is not set; use pipeline/bootstrap/with-shared-env.")
        with psycopg.connect(conninfo, connect_timeout=5) as conn:
            conn.execute("SELECT 1").fetchone()
        print("✓ PostgreSQL connection OK")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"✗ PostgreSQL connection failed: {exc}", file=sys.stderr)
        return False


def test_s3() -> bool:
    try:
        import boto3
        from botocore.config import Config

        client = boto3.client(
            "s3",
            endpoint_url=os.getenv("S3_ENDPOINT", "http://127.0.0.1:19000"),
            aws_access_key_id=os.getenv("S3_ACCESS_KEY"),
            aws_secret_access_key=os.getenv("S3_SECRET_KEY"),
            region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
            config=Config(s3={"addressing_style": "path"}),
        )
        client.list_buckets()
        print("✓ S3 connection OK")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"✗ S3 connection failed: {exc}", file=sys.stderr)
        return False


if __name__ == "__main__":
    raise SystemExit(0 if test_postgres() and test_s3() else 1)
