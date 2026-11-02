import traceback
import jiwer
import pandas as pd
from sentence_transformers import SentenceTransformer, util
from config import MODELO_EMBEDDING, PALAVRAS_POR_CHUNK
from transcricao import carregar_transcricoes_salvas

# --- Transformações do jiwer ---
base = [
    jiwer.ToLowerCase(),
    jiwer.RemovePunctuation(),
    jiwer.RemoveMultipleSpaces(),
    jiwer.Strip(),
]
transformacao_wer = jiwer.Compose(base + [jiwer.ReduceToListOfListOfWords()])
transformacao_cer = jiwer.Compose(base + [jiwer.ReduceToListOfListOfChars()])
_modelo_embedding = None


def get_modelo_embedding():
    global _modelo_embedding
    if _modelo_embedding is None:
        _modelo_embedding = SentenceTransformer(MODELO_EMBEDDING)
    return _modelo_embedding


def dividir_em_chunks(texto, palavras_por_chunk=80):
    palavras = texto.split()
    chunks = []

    for i in range(0, len(palavras), palavras_por_chunk):
        chunk = " ".join(palavras[i:i + palavras_por_chunk])
        chunks.append(chunk)

    return chunks if chunks else [""]


#Média dos embeddings dos chunks do texto
def embedding_texto_longo(texto):
    chunks = dividir_em_chunks(texto)
    embs = get_modelo_embedding().encode(chunks, convert_to_tensor=True)
    return embs.mean(dim=0)

# Retorna dict com wer, cer e similaridade_semantica entre dois textos
def calcular_similaridade(transcricao_1, transcricao_2):
    if not transcricao_1 or not transcricao_2:
        return {"wer": None, "cer": None, "similaridade_semantica": None}

    try:
        wer = jiwer.wer(
            transcricao_1, transcricao_2,
            reference_transform=transformacao_wer,
            hypothesis_transform=transformacao_wer,
        )
        cer = jiwer.cer(
            transcricao_1, transcricao_2,
            reference_transform=transformacao_cer,
            hypothesis_transform=transformacao_cer,
        )
    except Exception:
        print("Erro ao calcular WER/CER:")
        traceback.print_exc()
        wer, cer = None, None

    emb_1 = embedding_texto_longo(transcricao_1)
    emb_2 = embedding_texto_longo(transcricao_2)
    sim_semantica = util.cos_sim(emb_1, emb_2).item()

    return {"wer": wer, "cer": cer, "similaridade_semantica": sim_semantica}

# Compara as transcrições large x medium de cada áudio.
def gerar_dataframe_similaridade(caminho_large, caminho_medium):
    transcricoes_large = carregar_transcricoes_salvas(caminho_large)
    transcricoes_medium = carregar_transcricoes_salvas(caminho_medium)

    resultados = []
    for audio_id, d_large in transcricoes_large.items():
        if audio_id not in transcricoes_medium:
            continue  # ainda falta transcrever com o outro modelo

        d_medium = transcricoes_medium[audio_id]
        sim = calcular_similaridade(d_large["transcricao"], d_medium["transcricao"])

        resultados.append({
            "audio_id": audio_id,
            "duracao_seg": d_large["duracao_seg"],
            "transcricao_large": d_large["transcricao"],
            "tempo_large_seg": d_large["tempo_transcricao_seg"],
            "transcricao_medium": d_medium["transcricao"],
            "tempo_medium_seg": d_medium["tempo_transcricao_seg"],
            **sim,
        })

    return pd.DataFrame(resultados)