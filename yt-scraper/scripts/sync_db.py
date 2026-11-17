from collections import Counter
import configparser
import sys

import boto3
import psycopg2

BUCKET_PREFIX = "data/"
DEFAULT_LANGUAGE = "pt"

AUDIO_EXTS = {"mp3", "m4a", "wav", "ogg", "opus", "aac", "flac"}
SUBTITLE_EXTS = {"srt", "vtt"}
THUMB_EXTS = {"jpg", "jpeg", "png", "webp"}

INSERT_SQL = """
    INSERT INTO phd_pipeline.transcript
        (video_id, source_type, language_code, file_format,
         acquired_at, s3_bucket, bucket_key, size_bytes)
    VALUES (%s, %s, %s, %s, COALESCE(%s, now()), %s, %s, %s)
    ON CONFLICT (s3_bucket, bucket_key)
    DO UPDATE SET
        source_type = EXCLUDED.source_type,
        file_format = EXCLUDED.file_format,
        size_bytes = EXCLUDED.size_bytes;
"""


def load_config(conf_path="config.conf"):
    """Lê o arquivo de configuração ou encerra se ele não existir."""
    config = configparser.ConfigParser()
    if not config.read(conf_path, encoding="utf-8"):
        sys.exit(f"[ERRO] Arquivo '{conf_path}' nao encontrado.")
    return config


def scan_all_bucket_objects(s3, bucket, prefix=BUCKET_PREFIX):
    """
    Lista todos os objetos sob 'data/' de uma só vez e agrupa por youtube_video_id em memória.
    """
    grouped = {}
    paginator = s3.get_paginator("list_objects_v2")
    total_objects = 0

    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if not key.startswith(prefix) or key == prefix:
                continue

            rel = key[len(prefix) :]
            parts = rel.split("/", 1)
            if len(parts) < 2 or not parts[0] or not parts[1]:
                continue

            yt_id, sub_path = parts[0], parts[1]
            entry = grouped.setdefault(
                yt_id,
                {
                    "tags": set(),
                    "has_manual_sub": False,
                    "size_bytes": 0,
                    "latest_modified": None,
                },
            )

            total_objects += 1
            entry["size_bytes"] += obj.get("Size", 0)

            last_mod = obj.get("LastModified")
            if last_mod and (
                entry["latest_modified"] is None
                or last_mod > entry["latest_modified"]
            ):
                entry["latest_modified"] = last_mod

            lower_sub = sub_path.lower()
            if lower_sub.startswith("frames/"):
                entry["tags"].add("FRAMES")
            else:
                filename = lower_sub.rsplit("/", 1)[-1]
                ext = filename.rsplit(".", 1)[-1] if "." in filename else ""
                if ext in AUDIO_EXTS:
                    entry["tags"].add("AUDIO")
                elif ext in SUBTITLE_EXTS:
                    entry["tags"].add("SUBS")
                    if filename.startswith("manual_"):
                        entry["has_manual_sub"] = True
                elif ext in THUMB_EXTS:
                    entry["tags"].add("THUMB")

    print(
        f"[INFO] S3 escaneado: {total_objects} objetos em {len(grouped)} pastas de videos.",
        flush=True,
    )
    return grouped


def populate_transcript(conf_path="config.conf", dry_run=True):
    """Sincroniza em phd_pipeline.transcript os metadados consolidados de cada vídeo no bucket."""
    config = load_config(conf_path)
    bucket = config.get("S3", "bucket_name")
    port = config.get("S3", "port", fallback=None)
    endpoint_url = (
        f"{config.get('S3', 'endpoint')}:{port}"
        if port
        else config.get("S3", "endpoint")
    )

    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=config.get("S3", "access_key"),
        aws_secret_access_key=config.get("S3", "secret_key"),
    )

    print("[INFO] Listando objetos no S3...", flush=True)
    grouped_videos = scan_all_bucket_objects(s3, bucket, BUCKET_PREFIX)
    bucket_ids = sorted(grouped_videos.keys())

    conn = psycopg2.connect(
        host=config.get("POSTGRES", "host"),
        port=config.getint("POSTGRES", "port", fallback=5432),
        dbname=config.get("POSTGRES", "dbname"),
        user=config.get("POSTGRES", "user"),
        password=config.get("POSTGRES", "password"),
    )

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT youtube_video_id, id
                FROM phd_pipeline.video
                WHERE youtube_video_id = ANY(%s);
                """,
                (bucket_ids,),
            )
            video_pk_by_id = dict(cur.fetchall())

            cur.execute(
                "SELECT bucket_key FROM phd_pipeline.transcript WHERE s3_bucket = %s;",
                (bucket,),
            )
            existing_keys = {row[0] for row in cur.fetchall()}

            only_in_bucket = len(bucket_ids) - len(video_pk_by_id)
            print(
                f"[INFO] {len(bucket_ids)} pastas em '{BUCKET_PREFIX}' | "
                f"{len(video_pk_by_id)} presentes em phd_pipeline.video | "
                f"{only_in_bucket} apenas no bucket."
            )

            rows_to_sync, already_exist = [], 0
            for youtube_id in bucket_ids:
                video_pk = video_pk_by_id.get(youtube_id)
                if video_pk is None:
                    continue

                info = grouped_videos[youtube_id]
                ordered_tags = [
                    tag
                    for tag in ("AUDIO", "FRAMES", "SUBS", "THUMB")
                    if tag in info["tags"]
                ]
                file_format = (
                    ",".join(ordered_tags) if ordered_tags else "UNKNOWN"
                )
                source_type = (
                    "YOUTUBE_MANUAL"
                    if info["has_manual_sub"]
                    else "YOUTUBE_AUTOMATIC"
                )
                bucket_key = f"{BUCKET_PREFIX}{youtube_id}"

                if bucket_key in existing_keys:
                    already_exist += 1

                rows_to_sync.append({
                    "video_id": video_pk,
                    "source_type": source_type,
                    "language_code": DEFAULT_LANGUAGE,
                    "file_format": file_format,
                    "bucket_key": bucket_key,
                    "size_bytes": info["size_bytes"],
                    "acquired_at": info["latest_modified"],
                })

            print(
                f"[INFO] Total a sincronizar: {len(rows_to_sync)} | "
                f"Novos: {len(rows_to_sync) - already_exist} | "
                f"Ja existentes (serao atualizados): {already_exist}"
            )
            print(
                "[INFO] Distribuicao por file_format:"
                f" {dict(Counter(r['file_format'] for r in rows_to_sync))}"
            )
            for row in rows_to_sync[:5]:
                print(
                    f"  Exemplo: {row['file_format']:<22} | {row['source_type']:<17} | {row['bucket_key']}"
                )

            if not rows_to_sync:
                print("[OK] Nada a sincronizar.")
                return

            if dry_run:
                print(
                    "\n[DRY-RUN] Nenhuma alteracao aplicada. Rode com --apply para executar."
                )
                return

            affected = 0
            for row in rows_to_sync:
                cur.execute(
                    INSERT_SQL,
                    (
                        row["video_id"],
                        row["source_type"],
                        row["language_code"],
                        row["file_format"],
                        row["acquired_at"],
                        bucket,
                        row["bucket_key"],
                        row["size_bytes"],
                    ),
                )
                affected += cur.rowcount
            conn.commit()
            print(
                f"\n[SUCESSO] {affected} registros sincronizados em phd_pipeline.transcript!"
            )

    except Exception as e:
        conn.rollback()
        print(f"[ERRO] Falha durante a sincronizacao: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    populate_transcript(
        conf_path="config.conf", dry_run="--apply" not in sys.argv
    )