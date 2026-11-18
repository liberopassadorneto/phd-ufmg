import configparser
import sys
import psycopg2


def fix_s3_keys(conf_path="config.conf", dry_run=True):
    """Atualiza a coluna s3_key em phd_pipeline.transcript para 'data/<youtube_video_id>'."""
    config = configparser.ConfigParser()
    if not config.read(conf_path, encoding="utf-8"):
        print(f"[ERRO] Arquivo '{conf_path}' nao encontrado.")
        sys.exit(1)

    conn = psycopg2.connect(
        host=config.get("POSTGRES", "host"),
        port=config.getint("POSTGRES", "port", fallback=5432),
        dbname=config.get("POSTGRES", "dbname"),
        user=config.get("POSTGRES", "user"),
        password=config.get("POSTGRES", "password"),
    )

    try:
        with conn.cursor() as cur:
            # Verifica quantos registros têm caminho completo (ex: data/<id>/arquivo.ext ou data/<id>/frames/)
            cur.execute("""
                SELECT t.id, v.youtube_video_id, t.s3_key
                FROM phd_pipeline.transcript t
                JOIN phd_pipeline.video v ON v.id = t.video_id
                WHERE t.s3_key LIKE 'data/%/%';
            """)
            outdated_rows = cur.fetchall()

            print(f"[INFO] Registros encontrados com s3_key completo: {len(outdated_rows)}")
            for _, youtube_id, old_key in outdated_rows[:5]:
                print(f"  Exemplo: '{old_key}'  -->  'data/{youtube_id}'")

            if not outdated_rows:
                print("[OK] Nenhum registro precisa de atualizacao.")
                return

            if dry_run:
                print("\n[DRY-RUN] Nenhuma alteracao aplicada. Rode com --apply para executar.")
                return

            cur.execute("""
                UPDATE phd_pipeline.transcript t
                SET s3_key = 'data/' || v.youtube_video_id
                FROM phd_pipeline.video v
                WHERE v.id = t.video_id
                AND t.s3_key LIKE 'data/%/%';
            """)
            updated_count = cur.rowcount
            conn.commit()
            print(f"\n[SUCESSO] {updated_count} registros atualizados no banco!")

    except Exception as e:
        conn.rollback()
        print(f"[ERRO] Falha durante a atualizacao: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    apply_changes = "--apply" in sys.argv
    fix_s3_keys(conf_path="config.conf", dry_run=not apply_changes)