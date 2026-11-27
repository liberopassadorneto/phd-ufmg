"""Executa o pipeline completo: transcrição -> métricas -> legendas -> idioma -> análise."""
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import gc
import time
import torch
import whisper
import torch
from analise import (
    grafico_duracao_audios,
    grafico_similaridade_embedding,
    piores_casos,
    resumo_legendas,
    resumo_metricas,
    resumo_tempos,
    teste_wilcoxon,
)
from config import (
    CAMINHO_LARGE,
    CAMINHO_MEDIUM,
    CSV_IDIOMAS,
    CSV_LEGENDAS,
    CSV_TRANSCRICOES,
    MODELO_LARGE,
    MODELO_MEDIUM,
)
from idioma import detectar_todos, filtrar_suspeitos
from legendas import comparar_legendas, limpar_legendas_na_pasta
from metricas import gerar_dataframe_similaridade
from transcricao import (
    carregar_transcricoes_salvas,
    obter_duracao_audio,
    salvar_transcricao,
    transcrever_whisper,
)

def main():
    print(torch.cuda.is_available())  # deve retornar True
    print(torch.cuda.get_device_name(0))

    # ------- Transcrição --------------------------------------------
    audios_ids = listar_audios()
    # transcrever_modelo(audios_ids, "tiny", "tiny")
    transcrever_modelo(audios_ids, MODELO_MEDIUM, CAMINHO_MEDIUM)

    # # ------- Comparação large x medium ------------------------------
    # df_transcricoes = gerar_dataframe_similaridade("tiny", CAMINHO_MEDIUM)
    # df_transcricoes.to_csv(CSV_TRANSCRICOES, index=False)

    # resumo, df_exp = resumo_metricas(df_transcricoes)
    # print(resumo)
    # print(piores_casos(df_exp))
    # resumo_tempos(df_exp)
    # grafico_similaridade_embedding(df_exp)
    # grafico_duracao_audios(df_exp)

    # # ------- Comparação com legendas automáticas/manuais---------------
    # limpar_legendas_na_pasta()
    # df_legendas = comparar_legendas(df_transcricoes)
    # df_legendas.to_csv(CSV_LEGENDAS, index=False)
    # print(resumo_legendas(df_legendas))
    # teste_wilcoxon(df_legendas)

    # # ------- Verificação de idioma ------------------------------------
    # df_idiomas = detectar_todos(audios_ids)
    # df_idiomas.to_csv(CSV_IDIOMAS, index=False)
    # print(filtrar_suspeitos(df_idiomas))


if __name__ == "__main__":
    main()
