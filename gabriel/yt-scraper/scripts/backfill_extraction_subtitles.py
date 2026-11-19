import argparse
import configparser
import os
import sys
import boto3
import psycopg2
from psycopg2.extras import execute_batch


def load_configuration(conf_path: str) -> configparser.ConfigParser:
    """Lê e valida o arquivo de configuração .conf."""
    if not os.path.exists(conf_path):
        print(f"[ERRO] Arquivo de configuracao '{conf_path}' nao encontrado.")
        sys.exit(1)

    config = configparser.ConfigParser()
    config.read(conf_path, encoding="utf-8")
    return config


def build_s3_client(s3_config: dict):
    """Inicializa o cliente boto3 S3 com base nas configurações do .conf."""
    port = s3_config.get("port")
    endpoint_url = (
        f"{s3_config['endpoint']}:{port}" if port else s3_config["endpoint"]
    )
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=s3_config["access_key"],
        aws_secret_access_key=s3_config["secret_key"],
    )


def get_pg_connection(pg_config: dict):
    """Abre conexão com o banco PostgreSQL."""
    return psycopg2.connect(
        host=pg_config["host"],
        port=pg_config["port"],
        dbname=pg_config["dbname"],
        user=pg_config["user"],
        password=pg_config["password"],
    )


def detect_subtitle_source_type(
    s3_client, bucket_name: str, bucket_key: str
) -> str | None:
    """
    Inspeciona os arquivos no prefixo S3 do vídeo e determina o tipo da legenda:
    - 'YOUTUBE_MANUAL' se houver arquivo manual_*.srt/.vtt
    - 'YOUTUBE_AUTOMATIC' se houver arquivo automatic_*.srt/.vtt (ou outro .srt/.vtt)
    - None se nenhum arquivo de legenda existir no prefixo
    """
    prefix = bucket_key.rstrip("/") + "/"
    paginator = s3_client.get_paginator("list_objects_v2")

    subtitle_filenames = []
    for page in paginator.paginate(Bucket=bucket_name, Prefix=prefix):
        for obj in page.get("Contents", []):
            filename = os.path.basename(obj["Key"]).lower()
            if filename.endswith((".srt", ".vtt")):
                subtitle_filenames.append(filename)

    if not subtitle_filenames:
        return None

    if any(name.startswith("manual_") for name in subtitle_filenames):
        return "YOUTUBE_MANUAL"

    return "YOUTUBE_AUTOMATIC"


def main():
    parser = argparse.ArgumentParser(
        description="Restaura source_type e language_code em phd_pipeline.extraction via S3"
    )
    parser.add_argument(
        "--conf",
        type=str,
        default="config.conf",
        help="Caminho para o arquivo .conf (padrao: config.conf)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula a verificacao no S3 sem gravar alteracoes no PostgreSQL",
    )
    args = parser.parse_args()

    config = load_configuration(args.conf)

    s3_config = {
        "endpoint": config.get("S3", "endpoint"),
        "port": config.get("S3", "port", fallback=None),
        "access_key": config.get("S3", "access_key"),
        "secret_key": config.get("S3", "secret_key"),
        "bucket_name": config.get("S3", "bucket_name"),
    }

    pg_config = {
        "host": config.get("POSTGRES", "host"),
        "port": config.getint("POSTGRES", "port", fallback=5432),
        "dbname": config.get("POSTGRES", "dbname"),
        "user": config.get("POSTGRES", "user"),
        "password": config.get("POSTGRES", "password"),
    }

    s3_client = build_s3_client(s3_config)
    conn = get_pg_connection(pg_config)

    select_pending_sql = """
        SELECT id, s3_bucket, bucket_key
        FROM phd_pipeline.extraction
        WHERE source_type IS NULL
           OR language_code IS NULL
        ORDER BY id ASC;
    """

    update_sql = """
        UPDATE phd_pipeline.extraction
        SET source_type = %s,
            language_code = 'pt'
        WHERE id = %s;
    """

    try:
        with conn.cursor() as cur:
            cur.execute(select_pending_sql)
            rows = cur.fetchall()

        total = len(rows)
        print(f"[INIT] Registros com metadados pendentes encontrados: {total}")

        if total == 0:
            return

        updates = []
        manual_count = 0
        auto_count = 0
        no_subs_keys = []

        for idx, (row_id, s3_bucket, bucket_key) in enumerate(rows, start=1):
            target_bucket = s3_bucket or s3_config["bucket_name"]
            source_type = detect_subtitle_source_type(
                s3_client, target_bucket, bucket_key
            )

            if source_type == "YOUTUBE_MANUAL":
                manual_count += 1
                updates.append((source_type, row_id))
            elif source_type == "YOUTUBE_AUTOMATIC":
                auto_count += 1
                updates.append((source_type, row_id))
            else:
                no_subs_keys.append(bucket_key)

            if idx % 100 == 0 or idx == total:
                print(
                    f"[PROGRESSO] {idx}/{total} verificados | "
                    f"Manual: {manual_count} | Automatica: {auto_count} | "
                    f"Sem legenda no bucket: {len(no_subs_keys)}"
                )

        if args.dry_run:
            print(
                f"[DRY-RUN] Simulacao concluida. {len(updates)} registro(s) "
                "seriam atualizados."
            )
        elif updates:
            with conn:
                with conn.cursor() as cur:
                    execute_batch(cur, update_sql, updates, page_size=500)
            print(
                f"[SUCESSO] {len(updates)} registro(s) atualizados na tabela "
                "phd_pipeline.extraction."
            )

        if no_subs_keys:
            print(
                f"[AVISO] {len(no_subs_keys)} registro(s) nao possuem arquivo "
                ".srt/.vtt no S3 e permaneceram com source_type/language_code NULL."
            )

    finally:
        conn.close()


if __name__ == "__main__":
    main()