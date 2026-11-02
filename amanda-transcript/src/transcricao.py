import gc
import glob
import json
import os
import time
import traceback
import torch
import whisper
from mutagen.mp3 import MP3
from config import IDIOMA_TRANSCRICAO, PASTA_AUDIOS


def listar_audios(pasta=PASTA_AUDIOS):
    os.makedirs(pasta, exist_ok=True)
    ids = [
        os.path.splitext(os.path.basename(f))[0]
        for f in glob.glob(f"{pasta}/*.mp3")
    ]
    print(f"{len(ids)} áudios encontrados: {ids}")
    return ids


def transcrever_whisper(caminho_audio, modelo):
    if caminho_audio is None:
        return None
    try:
        result = modelo.transcribe(caminho_audio, language=IDIOMA_TRANSCRICAO)
        return result["text"]
    except Exception:
        print(f"Erro ao transcrever {caminho_audio}:")
        traceback.print_exc()
        return None


def obter_duracao_audio(caminho_audio):
    audio = MP3(caminho_audio)
    return audio.info.length  # em segundos


# Lê o .jsonl e retorna um dictionary {audio_id: dados_da_transcricao}
def carregar_transcricoes_salvas(caminho_arquivo):
    transcricoes = {}
    if os.path.exists(caminho_arquivo):
        with open(caminho_arquivo, "r", encoding="utf-8") as f:
            for linha in f:
                linha = linha.strip()
                if not linha:
                    continue
                dado = json.loads(linha)
                transcricoes[dado["audio_id"]] = dado
    return transcricoes

# Acrescenta uma transcrição ao arquivo e força a gravação na hora
def salvar_transcricao(caminho_arquivo, dado):
    with open(caminho_arquivo, "a", encoding="utf-8") as f:
        f.write(json.dumps(dado, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())

#  Transcreve audios_ids com o modelo indicado, pulando os que já
#  estão salvos em caminho_saida, e gravando cada novo resultado
#  assim que ele fica pronto.
def transcrever_modelo(audios_ids, modelo, caminho_saida, pasta_audios=PASTA_AUDIOS):
    ja_transcritos = carregar_transcricoes_salvas(caminho_saida)
    print(f"[{modelo}] {len(ja_transcritos)} áudios já transcritos anteriormente, retomando...")

    pendentes = [a for a in audios_ids if a not in ja_transcritos]
    if not pendentes:
        print(f"[{modelo}] nada pendente.")
        return ja_transcritos

    modelo_whisper = whisper.load_model(modelo)

    try:
        for audio_id in pendentes:
            caminho_audio = f"{pasta_audios}/{audio_id}.mp3"
            print(f"[{modelo}] Processando {audio_id}...")

            duracao = obter_duracao_audio(caminho_audio)
            inicio = time.time()
            transcricao = transcrever_whisper(caminho_audio, modelo_whisper)
            tempo = time.time() - inicio

            if transcricao is None:
                print(f"[{modelo}] FALHOU em {audio_id}, não será salvo")
                continue

            print(f"[{modelo}] {audio_id}: {tempo:.2f}s de processamento ({duracao:.2f}s de áudio)")

            dado = {
                "audio_id": audio_id,
                "duracao_seg": round(duracao, 2),
                "transcricao": transcricao,
                "tempo_transcricao_seg": round(tempo, 2),
            }

            salvar_transcricao(caminho_saida, dado)
            ja_transcritos[audio_id] = dado
    finally:
        # libera GPU/RAM antes de carregar o próximo modelo
        del modelo_whisper
        gc.collect()
        torch.cuda.empty_cache()

    return ja_transcritos