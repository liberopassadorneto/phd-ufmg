import argparse
from collections import Counter
import configparser
import csv
from datetime import datetime
import os
import random
import re
import time

import boto3
import psycopg2
import psycopg2.extras

from video_downloader import fetch_video_info, resolve_language

TABLE = "phd_pipeline.extraction"
VIDEO_TABLE = "phd_pipeline.video"
ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")
REQUIRED_COLUMNS = {"youtube_video_id", "s3_bucket", "bucket_key"}
CSV_FIELDS = [
    "video_id",
    "status",
    "language",
    "has_pt_orig",
    "source_type",
    "file_format",
    "size_bytes",
    "s3_bucket",
    "bucket_key",
    "error",
]
AUDIT_FIELDS = [
    "timestamp",
    "video_id",
    "language",
    "s3_bucket",
    "bucket_key",
    "objects_deleted",
    "db_rows_deleted",
]


def classify(info):
    """
    Classifica com o mesmo critério do video_downloader (language declarado e,
    sem ele, faixa '-orig' única). Retorna (status, language, has_pt_orig).
    Casos ambíguos ou sem informação ficam INDETERMINADO e nunca são apagados.
    """
    verdict, language, pt_orig_key = resolve_language(info)
    status = {"pt": "PORTUGUES", "foreign": "ESTRANGEIRO"}.get(verdict, "INDETERMINADO")
    return status, language, pt_orig_key is not None


def load_done_ids(csv_path):
    """IDs já classificados na planilha, exceto os com ERRO (que são refeitos)."""
    return {
        video_id
        for video_id, row in load_latest_rows(csv_path).items()
        if row["status"] != "ERRO"
    }


def connect_postgres(config):
    """Abre a conexão com o Postgres usando a seção [POSTGRES] do .conf."""
    return psycopg2.connect(
        host=config.get("POSTGRES", "host"),
        port=config.getint("POSTGRES", "port", fallback=5432),
        dbname=config.get("POSTGRES", "dbname"),
        user=config.get("POSTGRES", "user"),
        password=config.get("POSTGRES", "password"),
    )


def connect_s3(config):
    """Abre o cliente S3 compatível usando a seção [S3] do .conf."""
    endpoint = config.get("S3", "endpoint")
    port = config.get("S3", "port", fallback=None)
    secure = config.getboolean("S3", "secure", fallback=False)
    if not endpoint.startswith("http"):
        endpoint = f"{'https' if secure else 'http'}://{endpoint}"
    if port:
        endpoint = f"{endpoint}:{port}"
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=config.get("S3", "access_key"),
        aws_secret_access_key=config.get("S3", "secret_key"),
    )


def fetch_extractions(conn):
    """Lê os vídeos já extraídos (um registro por youtube_video_id)."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            f"""
            SELECT v.youtube_video_id, e.*
            FROM {TABLE} e
            JOIN {VIDEO_TABLE} v ON v.id = e.video_id
            """
        )
        rows = cur.fetchall()

    if rows:
        missing = REQUIRED_COLUMNS - set(rows[0].keys())
        if missing:
            raise SystemExit(
                f"[ERRO] Colunas ausentes em {TABLE}: {sorted(missing)}."
                f" Colunas encontradas: {sorted(rows[0].keys())}"
            )
    unique_rows = {}
    for row in rows:
        unique_rows.setdefault(row["youtube_video_id"], row)
    return list(unique_rows.values())


def classify_phase(db_rows, args):
    """Classifica o idioma (legenda automática original) de cada vídeo do banco, retomável."""
    done_ids = load_done_ids(args.output)
    pending = [r for r in db_rows if r["youtube_video_id"] not in done_ids]
    if args.limit:
        pending = pending[: args.limit]
    print(
        f"[INIT] Registros no banco: {len(db_rows)} | ja classificados:"
        f" {len(done_ids)} | pendentes: {len(pending)}"
    )

    is_new_file = not os.path.exists(args.output)
    with open(args.output, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, restval="")
        if is_new_file:
            writer.writeheader()

        for idx, row in enumerate(pending, start=1):
            video_id = row["youtube_video_id"]
            record = {
                "video_id": video_id,
                "source_type": row.get("source_type", ""),
                "file_format": row.get("file_format", ""),
                "size_bytes": row.get("size_bytes", ""),
                "s3_bucket": row.get("s3_bucket", ""),
                "bucket_key": row.get("bucket_key", ""),
            }
            try:
                info = fetch_video_info(video_id, args.proxy, args.cookies)
                status, language, has_pt_orig = classify(info)
                record.update(
                    status=status, language=language, has_pt_orig=has_pt_orig
                )
            except Exception as e:
                record.update(status="ERRO", error=repr(e)[:200])

            writer.writerow(record)
            f.flush()
            print(f"[{idx}/{len(pending)}] {video_id}: {record['status']}", flush=True)
            time.sleep(random.uniform(args.delay * 0.5, args.delay * 1.5))


def load_latest_rows(csv_path):
    """Última linha de cada vídeo na planilha (erros refeitos substituem os antigos)."""
    if not os.path.exists(csv_path):
        return {}
    with open(csv_path, encoding="utf-8", newline="") as f:
        return {row["video_id"]: row for row in csv.DictReader(f)}


def list_keys(s3, bucket, prefix):
    """Lista todas as chaves do bucket sob o prefixo informado."""
    keys = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        keys.extend(obj["Key"] for obj in page.get("Contents", []))
    return keys


def delete_keys(s3, bucket, keys):
    """Apaga as chaves em lotes de 1000 e levanta erro se alguma falhar."""
    for start in range(0, len(keys), 1000):
        batch = [{"Key": key} for key in keys[start : start + 1000]]
        response = s3.delete_objects(Bucket=bucket, Delete={"Objects": batch})
        if response.get("Errors"):
            raise RuntimeError(f"falha ao apagar objetos: {response['Errors'][:3]}")


def delete_phase(latest_rows, s3, conn, args, default_bucket=""):
    """Apaga do bucket e do banco os vídeos ESTRANGEIROS (dry-run, salvo com --apply)."""
    foreign_rows = [r for r in latest_rows.values() if r["status"] == "ESTRANGEIRO"]

    plan = []
    for row in foreign_rows:
        video_id = row["video_id"]
        # só apaga chaves no padrão data/<id> para nunca varrer o bucket inteiro
        if not ID_PATTERN.match(video_id) or row["bucket_key"] != f"data/{video_id}":
            print(f"[AVISO] {video_id}: chave fora do padrao ('{row['bucket_key']}'). Ignorado.")
            continue
        bucket = row["s3_bucket"] or default_bucket
        keys = list_keys(s3, bucket, f"{row['bucket_key']}/")
        if not keys:
            print(f"[AVISO] {video_id}: nenhum objeto em '{row['bucket_key']}/' no bucket.")
        plan.append((row, bucket, keys))

    total_objects = sum(len(keys) for _, _, keys in plan)
    print(
        f"\n[PLANO] Estrangeiros a apagar: {len(plan)} video(s),"
        f" {total_objects} objeto(s) no bucket + registros no banco."
    )
    for row, _, keys in plan[:20]:
        print(f"  {row['video_id']} ({row['language']}): {len(keys)} objeto(s)")
    if len(plan) > 20:
        print(f"  ... e mais {len(plan) - 20}")

    if not args.apply:
        print("\n[DRY-RUN] Nada foi apagado. Rode com --apply para executar.")
        return
    if not plan:
        return
    if not args.yes:
        answer = input(f"\nDigite APAGAR para remover {len(plan)} video(s): ")
        if answer.strip() != "APAGAR":
            print("[CANCELADO] Nada foi apagado.")
            return

    new_audit_file = not os.path.exists(args.audit)
    deleted = 0
    with open(args.audit, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=AUDIT_FIELDS)
        if new_audit_file:
            writer.writeheader()

        for row, bucket, keys in plan:
            video_id = row["video_id"]
            try:
                # banco primeiro, sem commit: se falhar (ex.: FK de content_screening)
                # o bucket não é tocado; se o bucket falhar, o rollback mantém o banco
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        DELETE FROM {TABLE}
                        WHERE video_id = (
                            SELECT id FROM {VIDEO_TABLE} WHERE youtube_video_id = %s
                        )
                        """,
                        (video_id,),
                    )
                    db_rows_deleted = cur.rowcount
                delete_keys(s3, bucket, keys)
                conn.commit()
            except Exception as e:
                conn.rollback()
                print(f"[ERRO] {video_id}: {e!r}. Registro do banco mantido.")
                continue

            writer.writerow(
                {
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "video_id": video_id,
                    "language": row["language"],
                    "s3_bucket": bucket,
                    "bucket_key": row["bucket_key"],
                    "objects_deleted": len(keys),
                    "db_rows_deleted": db_rows_deleted,
                }
            )
            f.flush()
            deleted += 1
            print(f"[APAGADO] {video_id} ({row['language']})", flush=True)

    print(f"\n[FIM] {deleted}/{len(plan)} video(s) apagados. Auditoria em '{args.audit}'.")


def main():
    parser = argparse.ArgumentParser(
        description="Audita o idioma dos videos ja baixados e apaga os estrangeiros"
    )
    parser.add_argument("--conf", default="config.conf", help="Arquivo .conf")
    parser.add_argument(
        "--output", default="audit_transcripts.csv", help="Planilha CSV de analise"
    )
    parser.add_argument(
        "--audit", default="audit_deleted.csv", help="CSV com o registro do que foi apagado"
    )
    parser.add_argument("--proxy", default="", help="Ex.: socks5h://127.0.0.1:1080")
    parser.add_argument("--cookies", default="", help="Arquivo de cookies Netscape")
    parser.add_argument(
        "--delay", type=float, default=2.0, help="Pausa media entre videos (s)"
    )
    parser.add_argument(
        "--limit", type=int, default=0, help="Classifica no maximo N videos (teste)"
    )
    parser.add_argument(
        "--apply", action="store_true", help="Apaga de verdade (padrao: dry-run)"
    )
    parser.add_argument(
        "--yes", action="store_true", help="Pula a confirmacao interativa do --apply"
    )
    args = parser.parse_args()

    config = configparser.ConfigParser()
    if not config.read(args.conf):
        raise SystemExit(f"[ERRO] Arquivo de configuracao nao encontrado: {args.conf}")

    conn = connect_postgres(config)
    try:
        db_rows = fetch_extractions(conn)
        classify_phase(db_rows, args)

        latest_rows = load_latest_rows(args.output)
        print("\n[RESUMO] Planilha:", dict(Counter(r["status"] for r in latest_rows.values())))

        s3 = connect_s3(config)
        delete_phase(
            latest_rows,
            s3,
            conn,
            args,
            default_bucket=config.get("S3", "bucket_name", fallback=""),
        )
    finally:
        conn.close()


if __name__ == "__main__":
    main()