#!/usr/bin/env python3
"""Download available Brazilian Portuguese YouTube caption tracks as SRT.

No video or audio is downloaded. SRT files are written to
``data/youtube/<video_id>/`` and uploaded to the configured S3 bucket.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

try:
    import yt_dlp
    from yt_dlp.utils import DownloadError
except ImportError:
    yt_dlp = None

    class DownloadError(Exception):
        pass


VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{6,}$")


class CollectorError(RuntimeError):
    """A controlled caption-collection error."""


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def extract_video_id(url: str) -> str | None:
    """Extract an ID from canonical, short, Shorts, embed, and live YouTube URLs."""
    parsed = urlparse(url)
    host = parsed.netloc.lower().split(":", 1)[0]
    candidate: str | None = None
    if host in {"youtu.be", "www.youtu.be"}:
        candidate = parsed.path.strip("/").split("/", 1)[0]
    elif host in {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}:
        if parsed.path == "/watch":
            candidate = parse_qs(parsed.query).get("v", [None])[0]
        else:
            parts = parsed.path.strip("/").split("/")
            if len(parts) >= 2 and parts[0] in {"shorts", "embed", "live"}:
                candidate = parts[1]
    return candidate if candidate and VIDEO_ID_RE.fullmatch(candidate) else None


def published_at(info: dict[str, Any]) -> str | None:
    if info.get("timestamp"):
        return datetime.fromtimestamp(info["timestamp"], tz=timezone.utc).date().isoformat()
    value = info.get("upload_date")
    if isinstance(value, str) and re.fullmatch(r"\d{8}", value):
        return f"{value[:4]}-{value[4:6]}-{value[6:]}"
    return None


def choose_caption_track(tracks: dict[str, Any], language: str = "pt-BR") -> str | None:
    """Prefer Brazilian Portuguese, accepting generic Portuguese as a fallback."""
    available = {str(key).lower(): str(key) for key, value in tracks.items() if value}
    selected = available.get(language.lower())
    if selected:
        return selected
    if language.lower() == "pt-br":
        return available.get("pt")
    return None


def base_source_record(video_id: str, url: str) -> dict[str, Any]:
    """Create the source metadata persisted with the caption object pointers."""
    return {
        "video_id": video_id,
        "youtube_url": url,
        "title": None,
        "channel_id": None,
        "channel_name": None,
        "published_at": None,
        "duration_seconds": None,
        "collected_at": now_iso(),
    }


def update_source_record(record: dict[str, Any], info: dict[str, Any]) -> None:
    record.update(
        {
            "video_id": info.get("id") or record["video_id"],
            "title": info.get("title"),
            "channel_id": info.get("channel_id"),
            "channel_name": info.get("channel") or info.get("uploader"),
            "published_at": published_at(info),
            "duration_seconds": int(info["duration"]) if info.get("duration") is not None else None,
        }
    )


def common_ydl_options() -> dict[str, Any]:
    return {"quiet": True, "no_warnings": True, "noplaylist": True, "skip_download": True}


def download_srt(
    url: str, directory: Path, video_id: str, language: str, track: str
) -> Path:
    assert yt_dlp is not None
    automatic = track == "automatic"
    temporary_directory = directory / f".{track}"
    temporary_directory.mkdir(parents=True, exist_ok=True)
    options = common_ydl_options() | {
        "outtmpl": str(temporary_directory / "%(id)s.%(ext)s"),
        "subtitleslangs": [language],
        "subtitlesformat": "srt/best",
        "writesubtitles": not automatic,
        "writeautomaticsub": automatic,
    }
    with yt_dlp.YoutubeDL(options) as ydl:
        if ydl.download([url]):
            raise CollectorError(f"yt-dlp failed to download the {track} caption track")
    files = sorted(temporary_directory.glob(f"{video_id}*.srt"))
    if not files:
        raise CollectorError(f"yt-dlp produced no SRT file for the {track} caption track")
    destination = directory / f"{track}.srt"
    files[0].replace(destination)
    return destination


def collect(args: argparse.Namespace) -> int:
    if yt_dlp is None:
        print('Missing dependency. Install project dependencies with: uv sync', file=sys.stderr)
        return 2
    video_id = extract_video_id(args.url)
    if not video_id:
        print("Unsupported YouTube video URL.", file=sys.stderr)
        return 2

    directory = Path(args.output_dir).expanduser() / video_id
    record = base_source_record(video_id, args.url)
    try:
        with yt_dlp.YoutubeDL(common_ydl_options()) as ydl:
            info = ydl.extract_info(args.url, download=False)
        if not isinstance(info, dict):
            raise CollectorError("yt-dlp did not return video metadata")
        update_source_record(record, info)
    except (DownloadError, CollectorError) as error:
        print(f"Source collection failed: {error}", file=sys.stderr)
        return 1

    manual_language = choose_caption_track(info.get("subtitles") or {})
    automatic_language = choose_caption_track(info.get("automatic_captions") or {})
    tracks: list[tuple[str, str]] = []
    if manual_language:
        tracks.append(("human", manual_language))
    if automatic_language:
        tracks.append(("automatic", automatic_language))
    if not tracks:
        print("No Brazilian Portuguese (pt-BR) manual or automatic caption track is available.", file=sys.stderr)
        return 1

    try:
        import psycopg

        conninfo = os.getenv("DATABASE_URL")
        if not conninfo:
            raise RuntimeError(
                "DATABASE_URL is not set; run the collector through "
                "the repository's scripts/run-yt-transcript helper."
            )
        with psycopg.connect(conninfo, connect_timeout=5) as conn:
            existing = conn.execute(
                "SELECT id FROM yt_transcript__youtube_sources WHERE video_id = %s",
                (record["video_id"],),
            ).fetchone()
        if existing and not args.force:
            print(f"Duplicate video_id {record['video_id']}; use --force to refresh it.", file=sys.stderr)
            return 0
    except Exception as error:  # noqa: BLE001 - report database failures to the CLI
        print(f"PostgreSQL lookup failed; check shared configuration and migrations: {error}", file=sys.stderr)
        return 1

    try:
        directory.mkdir(parents=True, exist_ok=True)
        srt_paths = {
            track: download_srt(args.url, directory, record["video_id"], language, track)
            for track, language in tracks
        }
    except (DownloadError, CollectorError, UnicodeDecodeError) as error:
        print(f"Caption collection failed: {error}", file=sys.stderr)
        return 1

    try:
        import boto3
        from botocore.config import Config

        bucket = args.s3_bucket
        srt_keys = {
            track: f"{record['video_id']}/{track}.srt" for track in srt_paths
        }
        s3 = boto3.client(
            "s3",
            endpoint_url=args.s3_endpoint,
            aws_access_key_id=args.s3_access_key,
            aws_secret_access_key=args.s3_secret_key,
            region_name=args.aws_region,
            config=Config(s3={"addressing_style": "path"}),
        )
        for track, srt_path in srt_paths.items():
            s3.upload_file(str(srt_path), bucket, srt_keys[track])

        with psycopg.connect(conninfo, connect_timeout=5) as conn:
            existing = conn.execute(
                "SELECT id FROM yt_transcript__youtube_sources WHERE video_id = %s",
                (record["video_id"],),
            ).fetchone()
            if existing:
                source_id = existing[0]
                conn.execute(
                    """UPDATE yt_transcript__youtube_sources SET
                           youtube_url = %s, title = %s, channel_id = %s,
                           channel_name = %s, published_at = %s,
                           duration_seconds = %s, collected_at = %s,
                           s3_bucket = %s, human_srt_key = %s,
                           automatic_srt_key = %s
                       WHERE id = %s""",
                    (
                        record["youtube_url"], record["title"], record["channel_id"],
                        record["channel_name"], record["published_at"],
                        record["duration_seconds"], record["collected_at"], bucket,
                        srt_keys.get("human"), srt_keys.get("automatic"), source_id,
                    ),
                )
            else:
                inserted = conn.execute(
                    """INSERT INTO yt_transcript__youtube_sources (
                           video_id, youtube_url, title, channel_id, channel_name,
                           published_at, duration_seconds, collected_at,
                           s3_bucket, human_srt_key, automatic_srt_key
                       ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                       RETURNING id""",
                    (
                        record["video_id"], record["youtube_url"], record["title"],
                        record["channel_id"], record["channel_name"],
                        record["published_at"], record["duration_seconds"],
                        record["collected_at"], bucket, srt_keys.get("human"),
                        srt_keys.get("automatic"),
                    ),
                ).fetchone()
                source_id = inserted[0]
    except Exception as error:  # noqa: BLE001 - report integration failures to the CLI
        print(f"Storage failed after SRT files were downloaded: {error}", file=sys.stderr)
        return 1

    print(f"Collected caption tracks for {record['video_id']} in {directory}")
    for track, key in srt_keys.items():
        print(f"Stored {track} SRT in s3://{bucket}/{key}")
    print("Stored video metadata and S3 object keys in the shared PostgreSQL database")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download available pt-BR caption tracks and store their S3 keys in the shared database."
    )
    parser.add_argument("--url", required=True, help="YouTube video URL")
    parser.add_argument("--output-dir", default="data/youtube", help="Output root (default: data/youtube)")
    parser.add_argument("--force", action="store_true", help="Replace records for an already-collected video ID")
    parser.add_argument(
        "--s3-endpoint",
        default=os.getenv("S3_ENDPOINT", "http://localhost:9000"),
        help="S3-compatible endpoint",
    )
    parser.add_argument("--s3-bucket", default=os.getenv("S3_BUCKET", "youtube-transcripts"))
    parser.add_argument("--s3-access-key", default=os.getenv("S3_ACCESS_KEY", "local"))
    parser.add_argument(
        "--s3-secret-key",
        default=os.getenv("S3_SECRET_KEY", "local-dev-secret-change-me"),
    )
    parser.add_argument("--aws-region", default=os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
    return parser


if __name__ == "__main__":
    raise SystemExit(collect(build_parser().parse_args()))
