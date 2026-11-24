import sys 
import os
import boto3
import time
from collections import Counter
from botocore.config import Config
from s3_audios import BUCKET_AUDIOS, cliente_s3

s3 = boto3.client(
    "s3",
    endpoint_url="http://127.0.0.1:19000",
    aws_access_key_id=os.environ["S3_ACCESS_KEY"],
    aws_secret_access_key=os.environ["S3_SECRET_KEY"],
    region_name="us-east-1",
    config=Config(s3={"addressing_style": "path"}),
)


# ========================================================================
# Listar os buckets 
# ========================================================================

# BUCKETS = ["youtube-transcripts", "youtube-assets-bucket"]
# LIMITE = 2

# for bucket in BUCKETS:
#     print(f"\n=== {bucket} ===")
#     achados = 0
#     total_visto = 0
#     for pagina in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket):
#         for obj in pagina.get("Contents", []):
#             total_visto += 1
#             if obj["Key"].lower().endswith(".mp3"):
#                 print(f'{obj["Size"]:>12}  {obj["Key"]}')
#                 achados += 1
#                 if achados >= LIMITE:
#                     break
#         if achados >= LIMITE:
#             break
#     print(f"({achados} .mp3 mostrados, {total_visto} objetos examinados)")


# ========================================================================
# Ver o que tem nos buckets 
# ========================================================================


BUCKET = "youtube-transcripts"
PREFIXO = sys.argv[1] if len(sys.argv) > 1 else ""   # opcional: um prefixo para filtrar
LIMITE = 50

s3 = cliente_s3()

# 1. "Pastas" de primeiro nível (prefixos) e objetos soltos na raiz
prefixos, raiz = [], []
for pag in s3.get_paginator("list_objects_v2").paginate(
        Bucket=BUCKET, Prefix=PREFIXO, Delimiter="/"):
    prefixos += [p["Prefix"] for p in pag.get("CommonPrefixes", [])]
    raiz += [(o["Size"], o["Key"]) for o in pag.get("Contents", [])]

print(f"Prefixos ({len(prefixos)}):")
for p in prefixos[:LIMITE]:
    print(f"  {p}")
print(f"\nObjetos neste nível ({len(raiz)}):")
for tam, key in raiz[:LIMITE]:
    print(f"  {tam:>10}  {key}")

# 2. Total de objetos e tamanho (percorre tudo, pode demorar se houver milhares)
total, soma = 0, 0
for pag in s3.get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix=PREFIXO):
    for o in pag.get("Contents", []):
        total += 1
        soma += o["Size"]
print(f"\nTotal: {total} objetos, {soma / 1e6:.1f} MB")

# ========================================================================
# Mostrar o que tem dentro de um item do bucket
# ========================================================================

s3 = cliente_s3()
obj = s3.get_object(Bucket="youtube-transcripts", Key="whisper/MwXmFG2hytc.txt")
print(obj["Body"].read().decode("utf-8")[:500])    # primeiros 500 caracteres