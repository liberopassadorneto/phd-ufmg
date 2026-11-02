def main() -> None:
    from yt_transcript.download_youtube_transcript import build_parser, collect

    raise SystemExit(collect(build_parser().parse_args()))
