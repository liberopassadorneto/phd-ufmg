import os
import psycopg2


def conectar():
    return psycopg2.connect(
        host="127.0.0.1",
        port=15432,                                         # porta do túnel
        dbname=os.environ.get("POSTGRES_DB", "phd_ufmg"),
        user=os.environ.get("POSTGRES_USER", "phd_ufmg"),
        password=os.environ["POSTGRES_PASSWORD"],
    )


def videos_pendentes(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT v.youtube_video_id, v.id, s.id,
                   s.language_prefilter_decision::text, s.default_language
            FROM phd_pipeline.video v
            LEFT JOIN phd_pipeline.whisper_transcript t ON t.video_id = v.id
            LEFT JOIN LATERAL (
                SELECT id, language_prefilter_decision, default_language, duration_seconds
                FROM phd_pipeline.video_metadata_snapshot
                WHERE video_id = v.id
                ORDER BY observed_at DESC
                LIMIT 1
            ) s ON true
            WHERE t.id IS NULL AND s.duration_seconds > 0
            
        """)
        # ORDER BY s.duration_seconds ASC NULLS LAST, v.id
        return {yt: (vid, snap, dec, lang)
                for yt, vid, snap, dec, lang in cur.fetchall()}


def descartar_video(conn, snapshot_id, idioma=None):
    if snapshot_id is None:
        return                      # vídeo sem snapshot: não há o que atualizar
    with conn.cursor() as cur:
        if idioma:
            cur.execute("""
                UPDATE phd_pipeline.video_metadata_snapshot
                SET default_language = %s, language_prefilter_decision = 'DISCARD'
                WHERE id = %s
            """, (idioma, snapshot_id))
        else:
            cur.execute("""
                UPDATE phd_pipeline.video_metadata_snapshot
                SET language_prefilter_decision = 'DISCARD'
                WHERE id = %s
            """, (snapshot_id,))
    conn.commit()


def registrar_transcricao(conn, video_id, model_version, segundos,
                          bucket, bucket_key, size_bytes):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO phd_pipeline.whisper_transcript 
                (video_id, file_format, model_version, transcription_seconds,
                 s3_bucket, bucket_key, size_bytes)
            VALUES (%s, 'txt', %s, %s, %s, %s, %s)
            ON CONFLICT (video_id) DO NOTHING
        """, (video_id, model_version, segundos, bucket, bucket_key, size_bytes))
    conn.commit()