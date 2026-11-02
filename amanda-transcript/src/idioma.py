"""Detecção de idioma usando só os primeiros 30s de cada áudio.

O Whisper converte o áudio em espectrograma Log-Mel (escala Mel para imitar a
percepção humana + escala logarítmica para a amplitude) e então detecta o idioma.
O modelo mais leve (tiny) já é suficiente para essa tarefa.
"""
import pandas as pd
import whisper
from config import LIMIAR_CONFIANCA_IDIOMA, MODELO_IDIOMA, PASTA_AUDIOS


def detectar_idioma(caminho_audio, model):
    audio = whisper.load_audio(caminho_audio)
    audio = whisper.pad_or_trim(audio)  # pega só 30s
    mel = whisper.log_mel_spectrogram(audio, n_mels=model.dims.n_mels).to(model.device)
    _, probs = model.detect_language(mel)
    idioma = max(probs, key=probs.get)
    return idioma, probs[idioma]


def detectar_todos(audios_ids, pasta_audios=PASTA_AUDIOS):
    """Detecta o idioma de cada áudio e retorna um DataFrame."""
    model = whisper.load_model(MODELO_IDIOMA)

    resultados = []
    for audio_id in audios_ids:
        print(f"Processando {audio_id}...")
        idioma, confianca = detectar_idioma(f"{pasta_audios}/{audio_id}.mp3", model)
        print(idioma, confianca)
        resultados.append({
            "audio_id": audio_id,
            "idioma": idioma,
            "confianca": confianca,
        })

    return pd.DataFrame(resultados)


# Os n áudios com menor confiança 
def piores_confiancas(df_idiomas, n=20):
    return df_idiomas.sort_values("confianca").head(n)

# Áudios que não são pt, ou são pt com confiança abaixo do limiar
def filtrar_suspeitos(df_idiomas, limiar=LIMIAR_CONFIANCA_IDIOMA):
    return df_idiomas[
        (df_idiomas["idioma"] != "pt")
        | ((df_idiomas["idioma"] == "pt") & (df_idiomas["confianca"] < limiar))
    ]