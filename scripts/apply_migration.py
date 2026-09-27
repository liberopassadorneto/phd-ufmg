#!/usr/bin/env python3
"""Apply the initial YouTube source-record migration to PostgreSQL/SPG."""

from __future__ import annotations

import os
from pathlib import Path

import psycopg


def main() -> None:
    conninfo = os.getenv(
        "DATABASE_URL", "host=localhost port=5432 dbname=postgres user=postgres"
    )
    migrations = sorted(
        (Path(__file__).resolve().parents[1] / "migrations").glob("*.sql")
    )
    with psycopg.connect(conninfo, connect_timeout=5) as conn:
        for migration in migrations:
            conn.execute(migration.read_text(encoding="utf-8"))
            print(f"Applied {migration.name}")


if __name__ == "__main__":
    main()
