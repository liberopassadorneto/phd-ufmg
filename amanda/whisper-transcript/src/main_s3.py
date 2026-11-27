import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import gc
import time
from collections import Counter
from importlib.metadata import version
import torch
import whisper
from config import MODELO_IDIOMA, MODELO_MEDIUM
from armazenamento import salvar_no_drive
from s3_audios import BUCKET_AUDIOS, achar_mp3, cliente_s3
from db import conectar, descartar_video, registrar_transcricao, videos_pendentes
from idioma import analisar_inicio, so_musica
from transcricao import (
    carregar_transcricoes_salvas,
    obter_duracao_audio,
    salvar_transcricao,
    transcrever_whisper,
)

PASTA_TEMP = "audios_temp"
CAMINHO_VERIFICADOS = "videos_verificados.jsonl"   # vídeos analisados e não transcritos
IDIOMA_ACEITO = "pt"
LIMITE = None          # vídeos analisados (transcritos ou não); None = todos
MODEL_VERSION = f"{version('openai-whisper')}/{MODELO_MEDIUM}"
def main():
    print("\n=========== PREPARANDO CONEXÃO ============\n")

    conn = conectar()
    s3 = cliente_s3()
    os.makedirs(PASTA_TEMP, exist_ok=True)

    pendentes = videos_pendentes(conn)
    verificados = carregar_transcricoes_salvas(CAMINHO_VERIFICADOS)

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
            if youtube_id in verificados:
                continue
            if LIMITE and analisados >= LIMITE:
                break

            temp = f"{PASTA_TEMP}/{youtube_id}.mp3"
            try:
                origem_audio = achar_mp3(s3, youtube_id)
                if origem_audio is None:
                    print(f"{youtube_id}: áudio não encontrado no S3")
                    continue
                print(f"\nBaixando {youtube_id} (filtro anterior: {decisao})...\n")
                s3.download_file(BUCKET_AUDIOS, origem_audio, temp)

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
                drive_path, arquivo_local = salvar_no_drive(youtube_id, corpo)
                registrar_transcricao(conn, video_id, MODEL_VERSION, round(tempo, 2),
                                      drive_path)
                try:
                    arquivo_local.unlink()
                except OSError as erro:
                    print(f"Não foi possível remover a cópia local {arquivo_local}: {erro}")
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
