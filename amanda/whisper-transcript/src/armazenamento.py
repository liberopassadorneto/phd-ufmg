"""Armazena e lê transcrições no Google Drive."""

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


def salvar_no_drive(youtube_id, corpo):
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
    return drive_path, caminho_local


def ler_transcricao(drive_path):
    resultado = subprocess.run(["rclone", "cat", drive_path],
                               check=True, capture_output=True, timeout=1800)
    return resultado.stdout.decode("utf-8")
