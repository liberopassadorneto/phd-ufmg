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


VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class CollectorError(RuntimeError):
    """A controlled caption-collection error."""


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


def choose_caption_track(tracks: dict[str, Any], language: str = "pt-BR") -> str | None:
    """Prefer Brazilian Portuguese, accepting generic Portuguese as a fallback."""
    available = {str(key).lower(): str(key) for key, value in tracks.items() if value}
    selected = available.get(language.lower())
    if selected:
        return selected
    if language.lower() == "pt-br":
        return available.get("pt")
    return None


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
    try:
        with yt_dlp.YoutubeDL(common_ydl_options()) as ydl:
            info = ydl.extract_info(args.url, download=False)
        if not isinstance(info, dict):
            raise CollectorError("yt-dlp did not return video metadata")
    except (DownloadError, CollectorError) as error:
        print(f"Caption-track discovery failed: {error}", file=sys.stderr)
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
        source_types = {
            "human": "YOUTUBE_MANUAL",
            "automatic": "YOUTUBE_AUTOMATIC",
        }
        with psycopg.connect(conninfo, connect_timeout=5) as conn:
            conn.execute("SET search_path TO phd_pipeline, public")
            video = conn.execute(
                "SELECT id FROM video WHERE youtube_video_id = %s",
                (video_id,),
            ).fetchone()
            if video is None:
                print(
                    f"Video {video_id} is not registered; run the earlier search/metadata stage first.",
                    file=sys.stderr,
                )
                return 1
            video_pk = video[0]
            existing = conn.execute(
                "SELECT source_type, language_code FROM transcript WHERE video_id = %s",
                (video_pk,),
            ).fetchall()
        existing_tracks = {(source_type, language) for source_type, language in existing}
        tracks = [
            (track, language)
            for track, language in tracks
            if args.force or (source_types[track], language) not in existing_tracks
        ]
        if not tracks:
            print(f"All available transcript tracks for {video_id} are already collected; use --force to refresh them.")
            return 0
    except Exception as error:  # noqa: BLE001 - report database failures to the CLI
        print(f"PostgreSQL lookup failed; check shared configuration and migrations: {error}", file=sys.stderr)
        return 1

    try:
        directory.mkdir(parents=True, exist_ok=True)
        srt_paths = {
            track: download_srt(args.url, directory, video_id, language, track)
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
            track: f"{video_id}/{track}.srt" for track in srt_paths
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
            conn.execute("SET search_path TO phd_pipeline, public")
            for track, srt_path in srt_paths.items():
                language = manual_language if track == "human" else automatic_language
                source_type = source_types[track]
                conn.execute(
                    """INSERT INTO transcript
                       (video_id, source_type, language_code, file_format, acquisition_tool,
                        acquisition_tool_version, s3_bucket, s3_key, size_bytes)
                       VALUES (%s, %s, %s, 'srt', 'yt-dlp', %s, %s, %s, %s)
                       ON CONFLICT (video_id, source_type, language_code) DO UPDATE SET
                         file_format = EXCLUDED.file_format,
                         acquisition_tool_version = EXCLUDED.acquisition_tool_version,
                         acquired_at = NOW(), s3_bucket = EXCLUDED.s3_bucket,
                         s3_key = EXCLUDED.s3_key, size_bytes = EXCLUDED.size_bytes""",
                    (video_pk, source_type, language, getattr(yt_dlp, "version", None),
                     bucket, srt_keys[track], srt_path.stat().st_size),
                )
    except Exception as error:  # noqa: BLE001 - report integration failures to the CLI
        print(f"Storage failed after SRT files were downloaded: {error}", file=sys.stderr)
        return 1

    print(f"Collected caption tracks for {video_id} in {directory}")
    for track, key in srt_keys.items():
        print(f"Stored {track} SRT in s3://{bucket}/{key}")
    print("Stored transcript records in the shared PostgreSQL database")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download available pt-BR caption tracks and store their S3 keys in the shared database."
    )
    parser.add_argument("--url", required=True, help="YouTube video URL")
    parser.add_argument("--output-dir", default="data/youtube", help="Output root (default: data/youtube)")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download and replace already-collected transcript tracks",
    )
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
