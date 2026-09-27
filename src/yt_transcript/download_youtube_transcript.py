#!/usr/bin/env python3
"""Download Brazilian Portuguese YouTube captions and create Step 1/2 pipeline records.

Install dependency:
    python -m pip install "yt-dlp[default]"

Example:
    python download_youtube_transcript.py \
      --url 'https://www.youtube.com/watch?v=VIDEO_ID'

No video or audio is downloaded. Output is written to
``data/youtube/<video_id>/`` by default.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
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
TIMESTAMP_RE = re.compile(
    r"^(?P<start>\d{1,2}:\d{2}:\d{2}[.,]\d{3}|\d{1,2}:\d{2}[.,]\d{3})"
    r"\s+-->\s+"
    r"(?P<end>\d{1,2}:\d{2}:\d{2}[.,]\d{3}|\d{1,2}:\d{2}[.,]\d{3})"
)
VTT_TAG_RE = re.compile(r"<[^>]+>")


class CollectorError(RuntimeError):
    """A controlled error that is persisted in the source record."""


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
    """Select only an explicitly labelled Brazilian Portuguese caption track."""
    available = {str(key).lower(): str(key) for key, value in tracks.items() if value}
    return available.get(language.lower())


def timestamp_seconds(value: str) -> float:
    parts = value.replace(",", ".").split(":")
    if len(parts) == 2:
        minutes, seconds = parts
        return int(minutes) * 60 + float(seconds)
    hours, minutes, seconds = parts
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def parse_vtt(vtt: str, video_id: str) -> list[dict[str, Any]]:
    """Map every non-empty VTT cue to a timestamped, cleaned transcript segment."""
    segments: list[dict[str, Any]] = []
    start: float | None = None
    end: float | None = None
    cue_lines: list[str] = []

    def finish_cue() -> None:
        nonlocal start, end, cue_lines
        if start is not None and end is not None:
            text = html.unescape(VTT_TAG_RE.sub("", " ".join(cue_lines)))
            text = re.sub(r"\s+", " ", text).strip()
            if text:
                segments.append(
                    {
                        "segment_id": f"{video_id}:{len(segments) + 1:06d}",
                        "start_seconds": start,
                        "end_seconds": end,
                        "text": text,
                    }
                )
        start = end = None
        cue_lines = []

    for raw_line in vtt.replace("\ufeff", "").splitlines():
        line = raw_line.strip()
        if match := TIMESTAMP_RE.match(line):
            finish_cue()
            start = timestamp_seconds(match["start"])
            end = timestamp_seconds(match["end"])
        elif not line:
            finish_cue()
        elif start is not None:
            cue_lines.append(line)
    finish_cue()
    return segments


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, content: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def base_source_record(video_id: str, url: str) -> dict[str, Any]:
    """Create the deliberately minimal source-record schema."""
    return {
        "video_id": video_id,
        "youtube_url": url,
        "title": None,
        "channel_id": None,
        "channel_name": None,
        "published_at": None,
        "duration_seconds": None,
        "collected_at": now_iso(),
        # "human" means creator-provided captions; "automatic" means
        # YouTube-generated captions.
        "transcript_source": None,
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


def download_vtt(url: str, directory: Path, video_id: str, language: str, automatic: bool) -> Path:
    assert yt_dlp is not None
    options = common_ydl_options() | {
        "outtmpl": str(directory / "%(id)s.%(ext)s"),
        "subtitleslangs": [language],
        "subtitlesformat": "vtt/best",
        "writesubtitles": not automatic,
        "writeautomaticsub": automatic,
    }
    with yt_dlp.YoutubeDL(options) as ydl:
        if ydl.download([url]):
            raise CollectorError("yt-dlp did not download the selected caption track")
    files = sorted(file for file in directory.glob(f"{video_id}*.vtt") if file.name != "transcript.vtt")
    if not files:
        raise CollectorError("yt-dlp completed without producing a VTT caption file")
    destination = directory / "transcript.vtt"
    files[0].replace(destination)
    return destination


def collect(args: argparse.Namespace) -> int:
    if yt_dlp is None:
        print('Missing dependency. Install it with: python -m pip install "yt-dlp[default]"', file=sys.stderr)
        return 2
    video_id = extract_video_id(args.url)
    if not video_id:
        print("Unsupported YouTube video URL.", file=sys.stderr)
        return 2

    directory = Path(args.output_dir).expanduser() / video_id
    source_path = directory / "video_source_record.json"
    if source_path.exists() and not args.force:
        print(f"Duplicate video_id {video_id}: existing record at {source_path}", file=sys.stderr)
        return 0

    directory.mkdir(parents=True, exist_ok=True)
    record = base_source_record(video_id, args.url)

    try:
        with yt_dlp.YoutubeDL(common_ydl_options()) as ydl:
            info = ydl.extract_info(args.url, download=False)
        if not isinstance(info, dict):
            raise CollectorError("yt-dlp did not return video metadata")
        update_source_record(record, info)
    except (DownloadError, CollectorError) as error:
        write_json(source_path, record)
        print(f"Source collection failed: {error}", file=sys.stderr)
        return 1

    manual_language = choose_caption_track(info.get("subtitles") or {})
    automatic_language = choose_caption_track(info.get("automatic_captions") or {})
    selected_language, automatic = (manual_language, False) if manual_language else (automatic_language, True)
    if not selected_language:
        write_json(source_path, record)
        print("No Brazilian Portuguese (pt-BR) manual or automatic caption track is available.", file=sys.stderr)
        return 1

    try:
        vtt_path = download_vtt(args.url, directory, record["video_id"], selected_language, automatic)
        segments = parse_vtt(vtt_path.read_text(encoding="utf-8"), record["video_id"])
        if not segments:
            raise CollectorError("the downloaded VTT contains no timestamped text cues")
    except (DownloadError, CollectorError, UnicodeDecodeError) as error:
        write_json(source_path, record)
        print(f"Caption collection failed: {error}", file=sys.stderr)
        return 1

    record["transcript_source"] = "automatic" if automatic else "human"
    write_json(source_path, record)
    write_json(
        directory / "transcript.json",
        {
            "video_id": record["video_id"],
            "youtube_url": record["youtube_url"],
            "collected_at": now_iso(),
            "caption_language": selected_language,
            "transcript_source": record["transcript_source"],
            "raw_vtt_file": "transcript.vtt",
            "raw_vtt_sha256": sha256_file(vtt_path),
            "segments": segments,
        },
    )
    print(f"Collected {len(segments)} segments for {record['video_id']} in {directory}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Download one YouTube transcript and write source/transcript records.")
    parser.add_argument("--url", required=True, help="YouTube video URL")
    parser.add_argument("--output-dir", default="data/youtube", help="Output root (default: data/youtube)")
    parser.add_argument("--force", action="store_true", help="Replace records for an already-collected video ID")
    return parser


if __name__ == "__main__":
    raise SystemExit(collect(build_parser().parse_args()))
