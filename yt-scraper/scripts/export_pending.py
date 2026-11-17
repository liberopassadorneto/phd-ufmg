import argparse
import configparser
import csv
import sys
import psycopg2


def load_configuration(conf_path: str) -> configparser.ConfigParser:
    """Lê o arquivo de configuração .conf."""
    config = configparser.ConfigParser()
    if not config.read(conf_path, encoding="utf-8"):
        print(f"[ERRO] Arquivo de configuracao '{conf_path}' nao encontrado.")
        sys.exit(1)
    return config


def export_pending_keep_videos(
    conf_path: str = "config.conf", output_csv: str | None = None
) -> None:
    """
    Busca todos os vídeos com language_prefilter_decision = 'KEEP' (no snapshot
    mais recente) que ainda não possuem registro em phd_pipeline.transcript e
    gera o CSV de entrada com a coluna 'video_id' para o manager.py.
    """
    config = load_configuration(conf_path)
    target_csv = output_csv or config.get(
        "DEFAULT", "csv_alvo", fallback="lista_alvos.csv"
    )

    conn = psycopg2.connect(
        host=config.get("POSTGRES", "host"),
        port=config.getint("POSTGRES", "port", fallback=5432),
        dbname=config.get("POSTGRES", "dbname"),
        user=config.get("POSTGRES", "user"),
        password=config.get("POSTGRES", "password"),
    )

    # Usa DISTINCT ON (video_id) ordenado por observed_at DESC para pegar
    # a decisão mais recente de cada vídeo caso existam múltiplos snapshots.
    query = """
        WITH latest_snapshots AS (
            SELECT DISTINCT ON (video_id)
                video_id,
                language_prefilter_decision
            FROM phd_pipeline.video_metadata_snapshot
            ORDER BY video_id, observed_at DESC
        )
        SELECT
            v.youtube_video_id,
            EXISTS (
                SELECT 1
                FROM phd_pipeline.transcript t
                WHERE t.video_id = v.id
            ) AS already_extracted
        FROM phd_pipeline.video v
        JOIN latest_snapshots ls ON ls.video_id = v.id
        WHERE ls.language_prefilter_decision = 'KEEP'
        ORDER BY v.id;
    """

    try:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()

        total_keep = len(rows)
        already_extracted = sum(1 for _, extracted in rows if extracted)
        pending_ids = [yt_id for yt_id, extracted in rows if not extracted]

        print(
            f"[INFO] Total marcados como KEEP: {total_keep} | "
            f"Ja extraidos (em transcript): {already_extracted} | "
            f"Pendentes para extracao: {len(pending_ids)}"
        )

        with open(target_csv, mode="w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["video_id"])
            for yt_id in pending_ids:
                writer.writerow([yt_id])

        print(
            f"[SUCESSO] CSV gerado em '{target_csv}' com {len(pending_ids)} video(s)."
        )

    except Exception as e:
        print(f"[ERRO] Falha ao consultar ou gerar CSV: {e}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Exporta vídeos KEEP ainda não extraídos para CSV."
    )
    parser.add_argument(
        "--conf",
        type=str,
        default="config.conf",
        help="Caminho para o arquivo .conf (padrão: config.conf)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Caminho de saída do CSV (se omitido, usa 'csv_alvo' do config.conf)",
    )
    args = parser.parse_args()

    export_pending_keep_videos(conf_path=args.conf, output_csv=args.output)