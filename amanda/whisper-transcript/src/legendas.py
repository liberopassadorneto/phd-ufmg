import glob
import os
import re
import shutil
import pandas as pd
from config import PASTA_LEGENDAS, PASTA_LEGENDAS_BACKUP, PREFIXOS_LEGENDA
from metricas import calcular_similaridade

# Transforma o conteúdo de um .srt em texto corrido.
def extrair_texto_srt(conteudo):
    conteudo = conteudo.replace("\r\n", "\n")
    linhas_texto = []

    for bloco in re.split(r"\n\s*\n", conteudo.strip()):
        linhas = bloco.split("\n")

        # fica só com o que vem depois da linha de tempo
        for i, l in enumerate(linhas):
            if "-->" in l:
                linhas = linhas[i + 1:]
                break
        else:
            continue  # bloco sem linha de tempo

        for l in linhas:
            l = re.sub(r"<[^>]+>", "", l)       # tags como <i> e <c>
            l = re.sub(r"\[[^\]]*\]", "", l)    # [Música], [Aplausos]
            l = l.replace("♪", "").strip()
            # legendas automáticas repetem a linha anterior no bloco seguinte
            if l and (not linhas_texto or l != linhas_texto[-1]):
                linhas_texto.append(l)

    return " ".join(linhas_texto)


def ja_limpo(conteudo):
    # um .srt original sempre tem linhas de tempo ("-->"), o limpo não tem
    return "-->" not in conteudo

# Converte os .srt da pasta em texto corrido (guardando backup do original).
def limpar_legendas_na_pasta(pasta=PASTA_LEGENDAS, pasta_backup=PASTA_LEGENDAS_BACKUP):
    os.makedirs(pasta_backup, exist_ok=True)
    limpas, ja_estavam, vazias = 0, 0, []

    for caminho in sorted(glob.glob(f"{pasta}/*.srt")):
        with open(caminho, "r", encoding="utf-8-sig") as f:
            conteudo = f.read()

        if ja_limpo(conteudo):
            ja_estavam += 1
            continue

        # backup do original antes de sobrescrever (não sobrescreve backup existente)
        destino = os.path.join(pasta_backup, os.path.basename(caminho))
        if not os.path.exists(destino):
            shutil.copy2(caminho, destino)

        texto = extrair_texto_srt(conteudo)
        if not texto:
            vazias.append(os.path.basename(caminho))

        with open(caminho, "w", encoding="utf-8") as f:
            f.write(texto)
        limpas += 1

    print(f"{limpas} legendas limpas agora, {ja_estavam} já estavam limpas.")
    if vazias:
        print(f"ATENÇÃO: ficaram legendas vazias depois da limpeza: {vazias}")

# Retorna {audio_id: {"automatic": texto, "manual": texto}} 
# só os que existirem
def carregar_legendas(pasta=PASTA_LEGENDAS):
    legendas = {}
    for caminho in glob.glob(f"{pasta}/*.srt"):
        nome = os.path.splitext(os.path.basename(caminho))[0]

        m = re.match(rf"^({'|'.join(PREFIXOS_LEGENDA)})_(.+)$", nome)
        if not m:
            print(f"Ignorado (nome fora do padrão automatic_/manual_): {nome}")
            continue
        tipo, audio_id = m.groups()

        with open(caminho, "r", encoding="utf-8-sig") as f:
            conteudo = f.read()
        texto = conteudo.strip() if ja_limpo(conteudo) else extrair_texto_srt(conteudo)

        legendas.setdefault(audio_id, {})[tipo] = texto
    return legendas

# Compara cada legenda (automatic/manual) com as transcrições large e medium.
def comparar_legendas(df_transcricoes, pasta_legendas=PASTA_LEGENDAS):
    legendas = carregar_legendas(pasta_legendas)

    sem_legenda = set(df_transcricoes["audio_id"]) - set(legendas)
    sem_audio = set(legendas) - set(df_transcricoes["audio_id"])
    if sem_legenda:
        print(f"{len(sem_legenda)} áudios sem nenhuma legenda: {sorted(sem_legenda)}")
    if sem_audio:
        print(f"{len(sem_audio)} legendas sem áudio correspondente: {sorted(sem_audio)}")

    resultados = []
    for _, linha in df_transcricoes.iterrows():
        audio_id = linha["audio_id"]

        # uma linha por áudio e por tipo de legenda
        for tipo, legenda in legendas.get(audio_id, {}).items():
            sim_large = calcular_similaridade(legenda, linha["transcricao_large"])
            sim_medium = calcular_similaridade(legenda, linha["transcricao_medium"])

            resultados.append({
                "audio_id": audio_id,
                "tipo_legenda": tipo,   # "automatic" ou "manual"
                "duracao_seg": linha["duracao_seg"],
                **{f"{k}_large": v for k, v in sim_large.items()},
                **{f"{k}_medium": v for k, v in sim_medium.items()},
            })

    return pd.DataFrame(resultados)