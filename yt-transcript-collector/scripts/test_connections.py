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
            raise RuntimeError(
                "DATABASE_URL is not set; run this check through "
                "the repository's scripts/with-shared-env helper."
            )
        with psycopg.connect(conninfo, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        print("✓ PostgreSQL connection OK")
        return True
    except Exception as exc:  # noqa: BLE001 - report connection failures clearly
        print(f"✗ PostgreSQL connection failed: {exc}", file=sys.stderr)
        return False


def test_s3() -> bool:
    try:
        import boto3

        client = boto3.client(
            "s3",
            endpoint_url=os.getenv("S3_ENDPOINT", "http://localhost:9000"),
            aws_access_key_id=os.getenv("S3_ACCESS_KEY", "local"),
            aws_secret_access_key=os.getenv(
                "S3_SECRET_KEY", "local-dev-secret-change-me"
            ),
            region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
        )
        client.list_buckets()
        print("✓ Local S3 connection OK")
        return True
    except Exception as exc:  # noqa: BLE001 - report connection failures clearly
        print(f"✗ Local S3 connection failed: {exc}", file=sys.stderr)
        return False


if __name__ == "__main__":
    postgres_ok = test_postgres()
    s3_ok = test_s3()
    raise SystemExit(0 if postgres_ok and s3_ok else 1)
