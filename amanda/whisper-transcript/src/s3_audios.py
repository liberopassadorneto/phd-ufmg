import os
import boto3
from botocore.config import Config

BUCKET_AUDIOS = "youtube-assets-bucket"
PREFIXO_AUDIOS = "data/" 

def cliente_s3():
    return boto3.client(
        "s3",
        endpoint_url=os.environ.get("S3_ENDPOINT", "http://127.0.0.1:19000"),
        aws_access_key_id=os.environ["S3_ACCESS_KEY"],
        aws_secret_access_key=os.environ["S3_SECRET_KEY"],
        region_name="us-east-1",
        config=Config(s3={"addressing_style": "path"}),
    )


def key_para_id(key):
    # ajuste conforme o padrão real das chaves
    partes = key.split("/")
    if len(partes) > 1:
        return partes[-2]                        # "ID/audio.mp3" -> "ID"
    return os.path.splitext(partes[0])[0]        # "ID.mp3" -> "ID"


def iter_mp3(s3, bucket=BUCKET_AUDIOS):
    vistos = 0
    for pagina in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket):
        vistos += len(pagina.get("Contents", []))
        print(f"  ... {vistos} objetos examinados")
        for obj in pagina.get("Contents", []):
            if obj["Key"].lower().endswith(".mp3"):
                yield key_para_id(obj["Key"]), obj["Key"]

def achar_mp3(s3, youtube_id, bucket=BUCKET_AUDIOS):
    """Chave do .mp3 desse vídeo no bucket, ou None se ainda não foi baixado."""
    prefixo = f"{PREFIXO_AUDIOS}{youtube_id}/"
    chaves = [obj["Key"] for pagina in s3.get_paginator("list_objects_v2").paginate(
        Bucket=bucket, Prefix=prefixo) for obj in pagina.get("Contents", [])
        if obj["Key"].lower().endswith(".mp3")]
    if len(chaves) > 1:
        raise ValueError(f"Mais de um áudio encontrado para {youtube_id} no S3")
    return chaves[0] if chaves else None
