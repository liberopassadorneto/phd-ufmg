import argparse
import configparser
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from storage_sync import StorageSyncManager, TranscriptRecord


def load_config(conf_path: Path) -> dict:
    """Lê as configurações do S3 e PostgreSQL a partir do .conf."""
    if not conf_path.exists():
        raise FileNotFoundError(f"Arquivo de configuracao nao encontrado: {conf_path}")

    config = configparser.ConfigParser()
    config.read(conf_path, encoding="utf-8")

    return {
        "s3": {
            "endpoint": config.get("S3", "endpoint"),
            "port": config.get("S3", "port", fallback=None),
            "access_key": config.get("S3", "access_key"),
            "secret_key": config.get("S3", "secret_key"),
            "bucket_name": config.get("S3", "bucket_name"),
        },
        "pg": {
            "host": config.get("POSTGRES", "host", fallback="127.0.0.1"),
            "port": config.getint("POSTGRES", "port", fallback=5432),
            "dbname": config.get("POSTGRES", "dbname"),
            "user": config.get("POSTGRES", "user"),
            "password": config.get("POSTGRES", "password"),
        },
    }


def list_s3_video_assets(
    s3_client, bucket_name: str, prefix: str = "data/"
) -> dict[str, list[dict]]:
    """
    Varre o bucket S3 e agrupa todos os objetos por youtube_video_id.
    Retorna {video_id: [{"key": str, "rel_path": str, "filename": str, "size_bytes": int}, ...]}.
    """
    s3_client.head_bucket(Bucket=bucket_name)

    assets_by_video: dict[str, list[dict]] = {}
    paginator = s3_client.get_paginator("list_objects_v2")

    for page in paginator.paginate(Bucket=bucket_name, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.endswith("/"):
                continue

            rel_path = key[len(prefix):] if key.startswith(prefix) else key
            parts = rel_path.split("/")
            if len(parts) < 2 or not parts[0]:
                continue

            video_id = parts[0]
            filename = parts[-1]
            assets_by_video.setdefault(video_id, []).append(
                {
                    "key": key,
                    "rel_path": rel_path,
                    "filename": filename,
                    "size_bytes": int(obj.get("Size", 0)),
                }
            )

    return assets_by_video


def infer_record_metadata(
    video_id: str,
    objects: list[dict],
    bucket_name: str,
    prefix: str = "data/",
) -> TranscriptRecord:
    """
    Infere file_format, source_type e size_bytes a partir dos arquivos
    presentes no bucket S3 para aquele video_id.
    """
    has_audio = False
    has_frames = False
    has_subs = False
    has_thumb = False
    has_manual_sub = False

    for obj in objects:
        fname = obj["filename"].lower()
        rel_path = obj["rel_path"].lower()

        if fname.endswith((".mp3", ".m4a", ".wav", ".opus")):
            has_audio = True
        elif "/frames/" in rel_path or fname.startswith("frame_"):
            has_frames = True
        elif fname.endswith((".srt", ".vtt")):
            has_subs = True
            if fname.startswith("manual_"):
                has_manual_sub = True
        elif fname.endswith((".jpg", ".jpeg", ".png", ".webp")):
            has_thumb = True

    tags = []
    if has_audio:
        tags.append("AUDIO")
    if has_frames:
        tags.append("FRAMES")
    if has_subs:
        tags.append("SUBS")
    if has_thumb:
        tags.append("THUMB")

    modality_str = ",".join(tags) if tags else "UNKNOWN"
    source_type = "YOUTUBE_MANUAL" if has_manual_sub else "YOUTUBE_AUTOMATIC"
    total_size_bytes = sum(o["size_bytes"] for o in objects)
    clean_prefix = prefix.rstrip("/")
    bucket_prefix_key = f"{clean_prefix}/{video_id}" if clean_prefix else video_id

    return TranscriptRecord(
        youtube_video_id=video_id,
        source_type=source_type,
        language_code="pt",
        file_format=modality_str,
        s3_bucket=bucket_name,
        bucket_key=bucket_prefix_key,
        size_bytes=total_size_bytes,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Reconcilia videos presentes no bucket S3 mas ausentes em phd_pipeline.extraction."
    )
    parser.add_argument(
        "--conf",
        type=Path,
        default=PROJECT_ROOT / "config.conf",
        help="Caminho para o arquivo config.conf (padrao: raiz do projeto)",
    )
    parser.add_argument(
        "--prefix",
        type=str,
        default="data/",
        help="Prefixo raiz no bucket S3 (padrao: data/)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula e exibe os registros que seriam inseridos sem gravar no DB",
    )
    args = parser.parse_args()

    cfg = load_config(args.conf)
    sync_manager = StorageSyncManager(pg_config=cfg["pg"], s3_config=cfg["s3"])

    print("[1/3] Buscando IDs ja registrados em phd_pipeline.extraction...")
    synced_ids = sync_manager.get_already_synced_youtube_ids()
    print(f">> {len(synced_ids)} ID(s) ja sincronizados no banco.")

    print(
        f"[2/3] Varrendo objetos no bucket '{sync_manager.bucket_name}' ({args.prefix})..."
    )
    s3_assets = list_s3_video_assets(
        sync_manager.s3, sync_manager.bucket_name, prefix=args.prefix
    )
    print(f">> {len(s3_assets)} pasta(s) de video encontradas no bucket.")

    orphan_ids = sorted(set(s3_assets.keys()) - synced_ids)
    print(f"[3/3] {len(orphan_ids)} ID(s) soltos no bucket (ausentes em extraction).")

    if not orphan_ids:
        print("[OK] Nada para reconciliar.")
        return

    inserted = 0
    not_in_video_table = 0
    errors = 0

    for video_id in orphan_ids:
        record = infer_record_metadata(
            video_id=video_id,
            objects=s3_assets[video_id],
            bucket_name=sync_manager.bucket_name,
            prefix=args.prefix,
        )

        if args.dry_run:
            print(
                f"[DRY-RUN] {record.youtube_video_id} | {record.file_format} | "
                f"{record.source_type} | {record.size_bytes} bytes | {record.bucket_key}"
            )
            inserted += 1
            continue

        try:
            extraction_id = sync_manager.save_transcript_to_db(record)
            inserted += 1
            print(
                f"[SYNC] {record.youtube_video_id} -> id={extraction_id} "
                f"({record.file_format} | {record.source_type})"
            )
        except ValueError as missing_err:
            not_in_video_table += 1
            print(f"[PULADO] {missing_err}")
        except Exception as exc:
            errors += 1
            print(f"[ERRO] Falha ao registrar {video_id}: {exc}")

    mode_label = "Simulados (dry-run)" if args.dry_run else "Registrados em extraction"
    print(
        f"\n[RESUMO] {mode_label}: {inserted} | "
        f"Ausentes em phd_pipeline.video: {not_in_video_table} | Erros: {errors}"
    )


if __name__ == "__main__":
    main()