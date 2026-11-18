import ast
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import MultipleLocator
from scipy.stats import wilcoxon
from config import PNG_DURACAO, PNG_SIMILARIDADE


# ---------- Transcrições large x medium ----------

def expandir_similaridade(df):
    if "similaridade" not in df.columns:
        return df

    def parse(x):
        return ast.literal_eval(x) if isinstance(x, str) else x

    sim = pd.DataFrame(df["similaridade"].apply(parse).tolist(), index=df.index)
    return pd.concat([df.drop(columns="similaridade"), sim], axis=1)


def resumo_metricas(df):
    df_exp = expandir_similaridade(df)
    colunas = ["wer", "cer", "similaridade_semantica"]
    resumo = df_exp[colunas].agg(["mean", "median", "std", "min", "max"]).T
    return resumo.round(4), df_exp

# Os n áudios com maior WER, com contagem de palavras de cada modelo
def piores_casos(df_exp, n=5):
    df = df_exp.copy()
    df["palavras_large"] = df["transcricao_large"].str.split().str.len()
    df["palavras_medium"] = df["transcricao_medium"].str.split().str.len()
    piores = df.sort_values("wer", ascending=False).head(n)
    return piores[["audio_id", "duracao_seg", "palavras_large", "palavras_medium",
                   "wer", "similaridade_semantica"]]


def _formatar(seg):
    h, resto = divmod(int(seg), 3600)
    m, s = divmod(resto, 60)
    return f"{h}h {m:02d}min {s:02d}s"


def resumo_tempos(df_exp):
    total_large = df_exp["tempo_large_seg"].sum()
    total_medium = df_exp["tempo_medium_seg"].sum()
    total_audio = df_exp["duracao_seg"].sum()

    print(f"Duração total dos áudios: {_formatar(total_audio)}")
    print(f"large-v1: {_formatar(total_large)}")
    print(f"medium:   {_formatar(total_medium)}")
    print(f"Razão large/medium: {total_large / total_medium:.2f}x")


# Barras da similaridade semântica por áudio, com linhas de média e mediana
def grafico_similaridade_embedding(df_exp, salvar_em=PNG_SIMILARIDADE,
                                   titulo="Similaridade semântica: Whisper large-v1 vs medium"):
    dados = df_exp.dropna(subset=["similaridade_semantica"]).sort_values("similaridade_semantica")
    media = dados["similaridade_semantica"].mean()
    mediana = dados["similaridade_semantica"].median()

    fig, ax = plt.subplots(figsize=(max(8, len(dados) * 0.3), 5))
    ax.bar(dados["audio_id"].astype(str), dados["similaridade_semantica"], color="#4C78A8")
    ax.axhline(media, color="#E45756", linestyle="--", label=f"Média: {media:.3f}")
    ax.axhline(mediana, color="#54A24B", linestyle=":", label=f"Mediana: {mediana:.3f}")

    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Similaridade do cosseno (embeddings)")
    ax.set_xlabel("Áudio")
    ax.set_title(titulo)
    ax.legend()
    plt.xticks(rotation=90)
    plt.tight_layout()

    if salvar_em:
        fig.savefig(salvar_em, dpi=150)
    plt.show()

# Histograma das durações dos áudios, com linhas de média e mediana (minutos)
def grafico_duracao_audios(df_exp, salvar_em=PNG_DURACAO, passo_min=5):
    duracao_min = df_exp["duracao_seg"] / 60
    media = duracao_min.mean()
    mediana = duracao_min.median()

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.hist(duracao_min, bins=20, color="#4C78A8", edgecolor="white")
    ax.axvline(media, color="#E45756", linestyle="--", label=f"Média: {media:.1f} min")
    ax.axvline(mediana, color="#54A24B", linestyle=":", label=f"Mediana: {mediana:.1f} min")

    ax.xaxis.set_major_locator(MultipleLocator(passo_min))
    ax.xaxis.set_minor_locator(MultipleLocator(1))
    ax.grid(axis="x", which="major", alpha=0.3)

    ax.set_xlabel("Duração do áudio (minutos)")
    ax.set_ylabel("Quantidade de áudios")
    ax.set_title("Distribuição da duração dos áudios")
    ax.legend()
    plt.tight_layout()

    if salvar_em:
        fig.savefig(salvar_em, dpi=150, bbox_inches="tight")
    plt.show()


# ---------- Legendas ----------

COLUNAS_LEGENDAS = [
    "wer_large", "wer_medium", "cer_large", "cer_medium",
    "similaridade_semantica_large", "similaridade_semantica_medium",
]


# Mediana das métricas por tipo de legenda, com a quantidade de áudios
def resumo_legendas(df_legendas):
    resumo = df_legendas.groupby("tipo_legenda")[COLUNAS_LEGENDAS].median().round(4)
    resumo["n_audios"] = df_legendas.groupby("tipo_legenda").size()
    return resumo


# Wilcoxon pareado do WER large x medium, separado por tipo de legenda
# compara o desempenho (medido pelo WER - Word Error Rate) entre o modelo
# Whisper large-v1 e o Whisper medium nos mesmos áudios
def teste_wilcoxon(df_legendas):
    for tipo, g in df_legendas.groupby("tipo_legenda"):
        g = g.dropna(subset=["wer_large", "wer_medium"])
        dif = g["wer_large"] - g["wer_medium"]   # positivo = medium melhor
        try:
            _, p = wilcoxon(dif, zero_method="zsplit")
        except ValueError as e:  # ex.: todas as diferenças iguais a zero
            print(f"{tipo}: não foi possível calcular Wilcoxon ({e})")
            continue
        print(f"{tipo}: n={len(g)}, mediana da diferença={dif.median():.4f}, p={p:.3f}, "
              f"medium melhor em {(dif > 0).sum()} de {len(g)} áudios")