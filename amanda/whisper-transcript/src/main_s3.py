import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import gc
import time
from collections import Counter
from importlib.metadata import version
import torch
import whisper
from config import MODELO_IDIOMA, MODELO_MEDIUM
from db import conectar, descartar_video, registrar_transcricao, videos_pendentes
from idioma import analisar_inicio, so_musica
from s3_audios import BUCKET_AUDIOS, cliente_s3, iter_mp3, achar_mp3
from transcricao import (
    carregar_transcricoes_salvas,
    obter_duracao_audio,
    salvar_transcricao,
    transcrever_whisper,
)

BUCKET_TRANSCRICOES = "youtube-transcripts"
PREFIXO_TRANSCRICOES = "whisper/"
PASTA_TEMP = "audios_temp"
CAMINHO_VERIFICADOS = "videos_verificados.jsonl"   # vídeos analisados e não transcritos
IDIOMA_ACEITO = "pt"
LIMITE = None          # vídeos analisados (transcritos ou não); None = todos
MODEL_VERSION = f"{version('openai-whisper')}/{MODELO_MEDIUM}"
CAMINHO_SEM_AUDIO = "sem_audio.txt"

def carregar_sem_audio():
    if os.path.exists(CAMINHO_SEM_AUDIO):
        with open(CAMINHO_SEM_AUDIO, encoding="utf-8") as f:
            return {linha.strip() for linha in f if linha.strip()}
    return set()

def main():
    print("\n=========== PREPARANDO CONEXÃO ============\n")

    s3 = cliente_s3()
    conn = conectar()
    os.makedirs(PASTA_TEMP, exist_ok=True)

    pendentes = videos_pendentes(conn)
    verificados = carregar_transcricoes_salvas(CAMINHO_VERIFICADOS)
    sem_audio = carregar_sem_audio()

    print(f"{len(pendentes)} vídeos sem transcrição no banco, "
          f"{len(verificados)} já verificados e não transcritos.")

    modelo_idioma = whisper.load_model(MODELO_IDIOMA)
    modelo = whisper.load_model(MODELO_MEDIUM)
    analisados = 0
    resumo = Counter()

    print("\n=========== PARA CADA AUDIO NÃO TRANSCRITO... ============\n")

    try:
        for n, (youtube_id, (video_id, snapshot_id, decisao, idioma_anterior)) in enumerate(pendentes.items(), 1):
            if n % 500 == 0:
                print(f"\n... {n} de {len(pendentes)} vídeos conferidos\n")
            if youtube_id in verificados or youtube_id in sem_audio:
                continue
            if LIMITE and analisados >= LIMITE:
                break

            key = achar_mp3(s3, youtube_id)
            if key is None:
                sem_audio.add(youtube_id)
                with open(CAMINHO_SEM_AUDIO, "a", encoding="utf-8") as f:
                    f.write(youtube_id + "\n")
                continue

            temp = f"{PASTA_TEMP}/{youtube_id}.mp3"
            try:
                print(f"\nBaixando {youtube_id} (filtro anterior: {decisao})...\n")
                s3.download_file(BUCKET_AUDIOS, key, temp)

                # Filtro do Whisper: roda em todos, inclusive nos já DISCARD
                idioma, confianca, texto = analisar_inicio(temp, modelo_idioma)
                musica = so_musica(texto)
                print(f"{youtube_id}: idioma={idioma} ({confianca:.2f}), "
                      f"música={musica}, início={texto[:60]!r}")

                if musica:
                    motivo = "musica"
                    descartar_video(conn, snapshot_id)             
                elif idioma != IDIOMA_ACEITO:
                    motivo = "idioma"
                    descartar_video(conn, snapshot_id, idioma)
                elif decisao == "DISCARD":
                    motivo = "discard_previo_whisper_diz_pt"    # só registra, não altera o banco
                else:
                    motivo = None

                if motivo:
                    salvar_transcricao(CAMINHO_VERIFICADOS, {
                        "audio_id": youtube_id,
                        "motivo": motivo,
                        "idioma": idioma,
                        "confianca": round(confianca, 4),
                        "texto_inicio": texto[:200],
                        "decisao_anterior": decisao,
                        "idioma_anterior": idioma_anterior,     # para reverter, se precisar
                    })
                    verificados[youtube_id] = True
                    resumo[motivo] += 1
                    analisados += 1
                    print(f"{youtube_id}: não transcrito ({motivo})")
                    continue

                # Passou nos dois filtros: transcreve
                duracao = obter_duracao_audio(temp)
                inicio = time.time()
                texto_final = transcrever_whisper(temp, modelo)
                tempo = time.time() - inicio
                if texto_final is None:
                    print(f"\nFALHOU em {youtube_id}, não será salvo\n")
                    continue

                corpo = texto_final.encode("utf-8")
                bucket_key = f"{PREFIXO_TRANSCRICOES}{youtube_id}.txt"
                s3.put_object(Bucket=BUCKET_TRANSCRICOES, Key=bucket_key,
                              Body=corpo, ContentType="text/plain; charset=utf-8")
                registrar_transcricao(conn, video_id, MODEL_VERSION, round(tempo, 2),
                                      BUCKET_TRANSCRICOES, bucket_key, len(corpo))
                resumo["transcrito"] += 1
                analisados += 1
                print(f"{youtube_id}: {tempo:.1f}s para {duracao:.1f}s de áudio.\n\n Salvo!!!")
                print("--------------------------------------------------------------------------------------------")
            except Exception as e:
                conn.rollback()
                print(f"\nErro em {youtube_id}: {e}\n")
            finally:
                if os.path.exists(temp):
                    os.remove(temp)
    finally:
        print("\nResumo:", dict(resumo))
        conn.close()
        del modelo, modelo_idioma
        gc.collect()
        torch.cuda.empty_cache()


if __name__ == "__main__":
    main()