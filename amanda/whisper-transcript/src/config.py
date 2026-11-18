
# --- Pastas ---
PASTA_AUDIOS = "audios"
PASTA_LEGENDAS = "legendas"
PASTA_LEGENDAS_BACKUP = "legendas_originais"  # backup dos .srt antes da limpeza

# --- Modelos Whisper ---
MODELO_LARGE = "large-v1"
MODELO_MEDIUM = "medium"
MODELO_IDIOMA = "tiny"         
IDIOMA_TRANSCRICAO = "pt"

# --- Saídas das transcrições (jsonl, retomáveis) ---
CAMINHO_LARGE = "transcricoes_large.jsonl"
CAMINHO_MEDIUM = "transcricoes_medium.jsonl"

# --- CSVs gerados ---
CSV_TRANSCRICOES = "transcricoes_whisper.csv"
CSV_LEGENDAS = "comparacao_legendas.csv"
CSV_IDIOMAS = "idiomas_detectados.csv"

# --- Gráficos ---
PNG_SIMILARIDADE = "similaridade_semantica.png"
PNG_DURACAO = "duracao_audios.png"

# --- Métricas ---
MODELO_EMBEDDING = "paraphrase-multilingual-MiniLM-L12-v2"
PALAVRAS_POR_CHUNK = 80

# --- Legendas ---
PREFIXOS_LEGENDA = ("automatic", "manual")

# --- Detecção de idioma ---
LIMIAR_CONFIANCA_IDIOMA = 0.95