from dataclasses import dataclass
import glob
import os
from typing import Optional
import boto3
from boto3.s3.transfer import TransferConfig
import psycopg2
import yt_dlp


@dataclass
class TranscriptRecord:
    """Schema contendo os metadados de extração para phd_pipeline.transcript."""

    youtube_video_id: str
    source_type: str  # 'YOUTUBE_MANUAL' ou 'YOUTUBE_AUTOMATIC'
    language_code: str
    file_format: str  # Ex: 'AUDIO', 'FRAMES', 'AUDIO,FRAMES' (baseado no .conf)
    s3_bucket: str
    s3_key: str
    size_bytes: Optional[int] = None
    acquisition_tool: str = "yt-dlp"
    acquisition_tool_version: Optional[str] = yt_dlp.version.__version__


class StorageSyncManager:
    """Gerencia a persistência no PostgreSQL (phd_pipeline) e o upload no S3."""

    def __init__(self, pg_config: dict, s3_config: dict):
        self.pg_config = pg_config
        self.bucket_name = s3_config["bucket_name"]
        port = s3_config.get("port")
        endpoint_url = (
            f"{s3_config['endpoint']}:{port}" if port else s3_config["endpoint"]
        )

        self.s3 = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=s3_config["access_key"],
            aws_secret_access_key=s3_config["secret_key"],
        )

    def _get_pg_connection(self):
        return psycopg2.connect(
            host=self.pg_config["host"],
            port=self.pg_config["port"],
            dbname=self.pg_config["dbname"],
            user=self.pg_config["user"],
            password=self.pg_config["password"],
        )

    def save_transcript_to_db(self, record: TranscriptRecord) -> int:
        """
        Busca o ID interno correspondente em phd_pipeline.video comparando
        youtube_video_id e insere/atualiza a linha em phd_pipeline.transcript.
        """
        select_video_sql = """
            SELECT id
            FROM phd_pipeline.video
            WHERE youtube_video_id = %s;
        """

        upsert_transcript_sql = """
            INSERT INTO phd_pipeline.transcript (
                video_id,
                source_type,
                language_code,
                file_format,
                acquisition_tool,
                acquisition_tool_version,
                s3_bucket,
                s3_key,
                size_bytes
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (video_id, source_type, language_code)
            DO UPDATE SET
                file_format = EXCLUDED.file_format,
                acquisition_tool = EXCLUDED.acquisition_tool,
                acquisition_tool_version = EXCLUDED.acquisition_tool_version,
                acquired_at = now(),
                s3_bucket = EXCLUDED.s3_bucket,
                s3_key = EXCLUDED.s3_key,
                size_bytes = EXCLUDED.size_bytes
            RETURNING id;
        """

        conn = self._get_pg_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(select_video_sql, (record.youtube_video_id,))
                    row = cur.fetchone()
                    if not row:
                        raise ValueError(
                            f"Vídeo '{record.youtube_video_id}' não encontrado"
                            " na tabela phd_pipeline.video."
                        )
                    internal_video_id = row[0]

                    cur.execute(
                        upsert_transcript_sql,
                        (
                            internal_video_id,
                            record.source_type,
                            record.language_code,
                            record.file_format,
                            record.acquisition_tool,
                            record.acquisition_tool_version,
                            record.s3_bucket,
                            record.s3_key,
                            record.size_bytes,
                        ),
                    )
                    transcript_id = cur.fetchone()[0]
                    return transcript_id
        finally:
            conn.close()

    def upload_video_assets_to_s3(
        self, youtube_video_id: str, video_folder: str
    ) -> list[dict]:
        """
        Envia todos os arquivos brutos da pasta local do vídeo para o bucket S3
        no padrão 'data/{youtube_video_id}/...' e retorna metadados dos uploads.
        """
        if not os.path.exists(video_folder):
            return []

        gb = 1024**3
        transfer_cfg = TransferConfig(multipart_threshold=5 * gb)
        uploaded_files = []

        for local_path in glob.glob(f"{video_folder}/**/*", recursive=True):
            if not os.path.isfile(local_path):
                continue

            rel_path_to_video = os.path.relpath(local_path, video_folder)
            s3_key = f"data/{youtube_video_id}/{rel_path_to_video}".replace(
                "\\", "/"
            )
            file_size = os.path.getsize(local_path)

            self.s3.upload_file(
                local_path,
                self.bucket_name,
                s3_key,
                Config=transfer_cfg,
            )

            uploaded_files.append({
                "local_path": local_path,
                "filename": os.path.basename(local_path),
                "s3_bucket": self.bucket_name,
                "s3_key": s3_key,
                "size_bytes": file_size,
            })

        return uploaded_files

    def get_already_synced_youtube_ids(self) -> set[str]:
        """Consulta phd_pipeline.transcript + video para pular vídeos já sincronizados."""
        query = """
            SELECT DISTINCT v.youtube_video_id
            FROM phd_pipeline.transcript t
            JOIN phd_pipeline.video v ON v.id = t.video_id;
        """
        conn = self._get_pg_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(query)
                return {row[0] for row in cur.fetchall()}
        except Exception:
            return set()
        finally:
            conn.close()