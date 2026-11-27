"""Armazena transcrições no Drive e referências no S3."""

import hashlib
import json
import os
import subprocess
import uuid
from pathlib import Path


def listar_audios_drive():
    destino = os.environ.get("DRIVE_OUTPUT_DESTINATION", "phd-drive:phd-ufmg").rstrip("/")
    raiz = os.environ.get("WHISPER_AUDIO_DRIVE", f"{destino}/amanda/whisper-transcript/audios").rstrip("/")
    resultado = subprocess.run(
        ["rclone", "lsjson", "--recursive", "--files-only", raiz],
        check=True, capture_output=True, timeout=1800,
    )
    audios = {}
    for arquivo in json.loads(resultado.stdout):
        caminho = Path(arquivo["Path"])
        if caminho.suffix.lower() != ".mp3":
            continue
        identificador = caminho.stem if len(caminho.stem) == 11 else caminho.parent.name
        if len(identificador) != 11:
            continue
        if identificador in audios:
            raise ValueError(f"Mais de um áudio encontrado para {identificador} no Drive")
        audios[identificador] = f"{raiz}/{arquivo['Path']}"
    return audios


def baixar_audio_drive(origem, destino):
    subprocess.run(["rclone", "copyto", origem, str(destino),
                    "--contimeout", "30s", "--timeout", "5m", "--retries", "3"],
                   check=True, timeout=1800)


def salvar_no_drive_e_s3(s3, bucket, youtube_id, corpo):
    destino = os.environ.get("DRIVE_OUTPUT_DESTINATION", "phd-drive:phd-ufmg").rstrip("/")
    identificador = uuid.uuid4().hex
    nome = f"{youtube_id}-{identificador}.txt"
    caminho_local = Path("transcricoes_pendentes") / nome
    caminho_local.parent.mkdir(parents=True, exist_ok=True)
    caminho_local.write_bytes(corpo)
    drive_path = f"{destino}/amanda/whisper-transcript/transcricoes/{nome}"
    subprocess.run(
        ["rclone", "copyto", str(caminho_local), drive_path,
         "--contimeout", "30s", "--timeout", "5m", "--retries", "3"],
        check=True, timeout=1800,
    )
    referencia = {
        "version": 1,
        "storage": "google_drive",
        "rclone_path": drive_path,
        "size_bytes": len(corpo),
        "sha256": hashlib.sha256(corpo).hexdigest(),
    }
    chave = f"whisper/references/{youtube_id}-{identificador}.json"
    s3.put_object(Bucket=bucket, Key=chave,
                  Body=json.dumps(referencia).encode("utf-8"),
                  ContentType="application/json")
    return chave, caminho_local


def ler_transcricao(s3, bucket, chave):
    objeto = s3.get_object(Bucket=bucket, Key=chave)
    corpo = objeto["Body"].read()
    if not chave.startswith("whisper/references/"):
        return corpo.decode("utf-8")
    referencia = json.loads(corpo)
    if referencia.get("version") != 1 or referencia.get("storage") != "google_drive":
        raise ValueError("Referência de transcrição desconhecida")
    resultado = subprocess.run(["rclone", "cat", referencia["rclone_path"]],
                               check=True, capture_output=True, timeout=1800)
    if (len(resultado.stdout) != referencia["size_bytes"] or
            hashlib.sha256(resultado.stdout).hexdigest() != referencia["sha256"]):
        raise ValueError("Transcrição no Drive não corresponde à referência S3")
    return resultado.stdout.decode("utf-8")
