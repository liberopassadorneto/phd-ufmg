# Resumo — Armazenamento e Formatos de Dados no Claim Extractor

## 1. Objetivo da discussão

Este chat consolidou decisões de engenharia de dados para o projeto de doutorado **Claim Extractor**, especialmente sobre:

- uso de **PostgreSQL** para dados operacionais;
- uso de **Apache Parquet** para datasets científicos e snapshots;
- relação entre esses formatos e as referências científicas usadas no projeto;
- diferença entre **dataset textual/estruturado** e **Binary Memory-Mapped** para execução e treinamento de LLMs.

---

## 2. PostgreSQL vs. Parquet

PostgreSQL e Parquet não são substitutos diretos: eles resolvem problemas diferentes.

### PostgreSQL

Mais adequado para o **estado operacional e mutável** da pipeline:

- registro de vídeos coletados;
- status de download;
- status de transcrição;
- controle de processamento;
- atualizações frequentes;
- consultas por `video_id`;
- prevenção de processamento duplicado;
- versionamento lógico de registros e estados.

Exemplo de entidade:

```text
youtube_videos
--------------
video_id
title
channel_id
published_at
duration
language
download_status
transcript_status
transcript_version
collected_at
updated_at
```

### Apache Parquet

Mais adequado para o **estado científico, analítico e reproduzível** do dataset:

- snapshots imutáveis;
- análise com DuckDB, Polars, PyArrow e Pandas;
- seleção eficiente de colunas;
- compressão;
- datasets de treino/validação/teste;
- compartilhamento de datasets;
- experimentos reproduzíveis.

Arquitetura recomendada:

```text
YouTube API / yt-dlp
        ↓
     PostgreSQL
        ↓
estado operacional
        ↓
export / snapshot
        ↓
     Parquet
        ↓
Claim Extraction / ML / análise
```

---

## 3. Parquet como snapshot científico

Um dos usos mais adequados de Parquet neste projeto é criar um **snapshot congelado do dataset em determinado ponto no tempo**.

Exemplo:

```text
dataset_v1/
├── videos.parquet
├── transcripts.parquet
├── claims.parquet
└── annotations.parquet
```

Metadados possíveis:

```text
dataset_version: v1
created_at: 2026-09-30
pipeline_version: claim-extractor-v0.1
source_videos: 100
claims: 1842
```

A ideia é separar:

```text
PostgreSQL
= current state / estado operacional

Parquet snapshot
= frozen experimental state / estado científico congelado
```

Assim, diferentes experimentos podem usar exatamente o mesmo dataset:

```text
Experimento E1 → dataset_v1
Experimento E2 → dataset_v1
```

Mesmo que a pipeline evolua posteriormente para `dataset_v2`.

Importante: **Parquet não faz versionamento sozinho**. O versionamento deve ser controlado por convenção de diretórios, DVC, Git/LFS, LakeFS, object storage ou mecanismo equivalente.

---

## 4. Uso de Parquet nas referências científicas

Foi verificado se Parquet aparece explicitamente nas principais referências usadas no projeto.

### Resultado geral

Não foi identificada evidência de que **Parquet seja parte central da metodologia científica** dessas referências.

Os formatos observados são principalmente:

```text
FEVER        → JSONL
FActScore    → JSONL
X-CLAIM      → CSV
outros       → arquivos próprios / formatos do código
```

Referências analisadas:

1. Thorne et al. (2018) — FEVER
2. Choi et al. (2021) — Decontextualization
3. Sundriyal et al. (2022) — Claim Span Identification
4. Min et al. (2023) — FActScore
5. Sundriyal et al. (2023) — Claim Normalization / CLAN / CACN
6. Mittal et al. (2023) — X-CLAIM
7. Deng et al. (2024) — Document-level Claim Extraction and Decontextualisation
8. Ullrich et al. (2025) — FEVERFact

Conclusão:

> O uso de Parquet no projeto deve ser tratado como uma **decisão de engenharia de dados**, e não como uma exigência metodológica herdada desses papers.

---

## 5. Metodologia científica ≠ formato físico

É importante separar dois níveis:

```text
Metodologia científica
-----------------------
claims
labels
splits
provenance
annotation protocol
metrics
models
prompts
versions

           ≠

Formato físico
--------------
JSONL
CSV
Parquet
PostgreSQL
```

A metodologia pode ser reproduzível independentemente de o dataset estar armazenado em JSONL, CSV ou Parquet.

---

## 6. Dataset textual vs. Binary Memory-Mapped

A LLM do Claim Extractor não precisa receber diretamente dados em formato Binary Memory-Mapped.

Para inferência e experimentação normal:

```text
Parquet / PostgreSQL / JSONL
        ↓
DataLoader
        ↓
Tokenizer
        ↓
LLM / modelo
        ↓
Claims
```

O **Binary Memory-Mapped** é mais relevante para treinamento em grande escala, especialmente pre-training ou fine-tuning intensivo:

```text
Dataset textual
     ↓
tokenização offline
     ↓
.bin / .idx / MDS / mmap
     ↓
GPU training loop
```

Portanto:

```text
Parquet
= dataset científico / snapshot / curadoria

Binary Memory-Mapped
= representação opcional otimizada para treinamento
```

A LLM continua conceitualmente usando o mesmo dataset; o formato binário é apenas uma representação pré-tokenizada e otimizada para throughput.

---

## 7. Arquitetura recomendada para o Claim Extractor

```text
                DATA LAYER

PostgreSQL
   ↓
Parquet snapshot
   ↓
train / validation / test
   ↓
────────────────────────
      MODEL PIPELINE
────────────────────────
   ↓
DataLoader
   ↓
Tokenizer
   ↓
CSI / Atomic / Norm / Decontext
   ↓
CLAIM DATASET
```

O uso de `.bin`, `.idx`, MDS ou outro formato memory-mapped só deve ser introduzido se o volume de treinamento justificar a complexidade adicional.

---

## 8. Decisão consolidada

Para o projeto atual:

- **PostgreSQL** → controle operacional da coleta e processamento;
- **Parquet** → snapshots científicos, análise, experimentos e versionamento do dataset;
- **JSONL** → formato de intercâmbio, export, compatibilidade e reprodução;
- **Binary Memory-Mapped** → opcional, apenas quando o treinamento exigir throughput de I/O significativamente maior.

A recomendação é começar com **PostgreSQL + Parquet + JSONL** e adiar Binary Memory-Mapped até existir uma necessidade concreta de otimização do treinamento.
