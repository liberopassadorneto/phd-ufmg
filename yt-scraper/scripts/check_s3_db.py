import csv
import configparser
import boto3
import psycopg2
from psycopg2.extras import RealDictCursor


def load_config(conf_path="config.conf"):
    config = configparser.ConfigParser()
    config.read(conf_path, encoding="utf-8")

    return {
        "s3": {
            "endpoint": config.get("S3", "endpoint"),
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


def get_video_ids_from_s3(s3_cfg, prefix="data/"):
    """Lista os video_id únicos armazenados sob o prefixo 'data/<video_id>/' no bucket."""
    s3 = boto3.client(
        "s3",
        endpoint_url=s3_cfg["endpoint"],
        aws_access_key_id=s3_cfg["access_key"],
        aws_secret_access_key=s3_cfg["secret_key"],
    )

    print(f"Conectando ao bucket '{s3_cfg['bucket_name']}' em {s3_cfg['endpoint']}...")
    s3.head_bucket(Bucket=s3_cfg["bucket_name"])

    video_ids = set()
    paginator = s3.get_paginator("list_objects_v2")

    # Delimiter='/' retorna apenas os subdiretórios imediatos (CommonPrefixes) em data/
    for page in paginator.paginate(
        Bucket=s3_cfg["bucket_name"], Prefix=prefix, Delimiter="/"
    ):
        for cp in page.get("CommonPrefixes", []):
            # Exemplo de cp['Prefix']: 'data/dQw4w9WgXcQ/' -> extrai 'dQw4w9WgXcQ'
            folder_path = cp["Prefix"].rstrip("/")
            video_id = folder_path.split("/")[-1]
            if video_id:
                video_ids.add(video_id)

    # Fallback caso os objetos estejam na raiz do bucket e não sob 'data/'
    if not video_ids and prefix:
        print(f"Nenhuma pasta encontrada em '{prefix}'. Verificando na raiz do bucket...")
        for page in paginator.paginate(Bucket=s3_cfg["bucket_name"], Delimiter="/"):
            for cp in page.get("CommonPrefixes", []):
                video_id = cp["Prefix"].rstrip("/")
                if video_id and video_id != "data":
                    video_ids.add(video_id)

    print(f"✓ {len(video_ids)} video_id(s) únicos encontrados no bucket S3.")
    return sorted(video_ids)


def fetch_matching_rows_from_db(pg_cfg, video_ids, batch_size=1000):
    """Consulta phd_pipeline.video_metadata_snapshot retornando as linhas presentes no bucket."""
    if not video_ids:
        return []

    print("Conectando ao PostgreSQL e cruzando com phd_pipeline.video_metadata_snapshot...")
    conn = psycopg2.connect(**pg_cfg)
    matched_rows = []

    query = """
        SELECT *
        FROM phd_pipeline.video_metadata_snapshot
        WHERE video_id = ANY(%s)
        ORDER BY video_id;
    """

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            for i in range(0, len(video_ids), batch_size):
                batch = video_ids[i : i + batch_size]
                cur.execute(query, (batch,))
                matched_rows.extend(cur.fetchall())
    finally:
        conn.close()

    print(f">> {len(matched_rows)} linhas correspondente(s) encontrada(s) no banco de dados.")
    return matched_rows


def export_to_csv(rows, output_csv="videos_presentes_bucket_db.csv"):
    if not rows:
        print("Nenhuma correspondência encontrada. O arquivo CSV não foi gerado.")
        return

    fieldnames = list(rows[0].keys())
    with open(output_csv, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f">> CSV gerado com sucesso: '{output_csv}' ({len(rows)} registros).")


if __name__ == "__main__":
    cfg = load_config("config.conf")

    s3_video_ids = get_video_ids_from_s3(cfg["s3"], prefix="data/")
    db_rows = fetch_matching_rows_from_db(cfg["pg"], s3_video_ids)
    export_to_csv(db_rows, output_csv="videos_presentes_bucket_db.csv")

    # Resumo rápido de divergências
    db_video_ids = {row["video_id"] for row in db_rows}
    apenas_no_bucket = set(s3_video_ids) - db_video_ids
    print(f"Resumo: {len(db_video_ids)} no bucket e no DB | {len(apenas_no_bucket)} apenas no bucket.")