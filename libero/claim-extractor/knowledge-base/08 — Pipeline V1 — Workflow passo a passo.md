# Pipeline V1 — Workflow Step by Step

## 1. Contexto e objetivo

O objetivo desta etapa do projeto de doutorado é definir uma metodologia reprodutível para transformar vídeos sobre semaglutida e outros medicamentos GLP-1 em um **Claim Dataset** estruturado.

A abordagem segue o princípio **divide and conquer**: a Pipeline V1 é dividida em etapas menores, cada uma com objetivo, técnica, entrada, saída e critérios de aceite. Cada step deve ser revisado e aprovado pelo pesquisador antes do avanço para o seguinte.

O escopo atual é **Claim Extraction**. Classificação temática e verificação de veracidade são fases posteriores e independentes.

```text
Transcript
   ↓
Claim Extraction
   ↓
Claim Dataset
   ↓
Claim Classification / Verification
```

Essa separação permite identificar e avaliar independentemente erros de extração, classificação e verificação.

---

## 2. Pipeline V1 — visão enxuta

```text
+----------------------+
|    YouTube Video     |
+----------+-----------+
           |
           v
+----------------------+
|      Transcript      |
+----------+-----------+
           |
           v
+----------------------+
| Transcript Processing|
+----------+-----------+
           |
           v
+----------------------+
|    CLAIM DATASET     |
+----------------------+
```

A etapa `Transcript Processing` concentra os processos metodológicos internos:

```text
Source Provenance
      ↓
Context Window
      ↓
Claim Span Identification
      ↓
Atomic Claim Decomposition
      ↓
Claim Normalization
      ↓
Decontextualization
      ↓
Faithfulness Validation
      ↓
Deduplication / Consolidation
```

---

## 3. Checklist do workflow

- [ ] Step 1 — Aquisição e catalogação do vídeo
- [ ] Step 2 — Obtenção e alinhamento temporal do transcript
- [ ] Step 3 — Limpeza e segmentação do transcript
- [ ] Step 4 — Construção da Context Window
- [ ] Step 5 — Claim Span Identification
- [ ] Step 6 — Atomic Claim Decomposition
- [ ] Step 7 — Claim Normalization
- [ ] Step 8 — Decontextualization
- [ ] Step 9 — Faithfulness Validation
- [ ] Step 10 — Deduplication / Consolidation
- [ ] Step 11 — Construção e controle de qualidade do Claim Dataset

O workflow é incremental: somente o Step 1 foi detalhado até o momento e ainda depende do aceite formal do pesquisador.

---

## 4. Step 1 — Aquisição e catalogação do vídeo

### 4.1 Objetivo

Registrar cada vídeo como uma fonte de dados rastreável e reproduzível antes da obtenção do transcript.

O Step 1 não extrai claims, não classifica conteúdo e não verifica veracidade. Seu resultado é um registro persistente da fonte.

```text
YouTube Video
      ↓
Source Registration
      ↓
VideoSourceRecord
```

### 4.2 Fundamentação metodológica

- **Thorne et al. (2018) — FEVER:** preserva a ligação entre claims e sentenças de evidência, fundamentando a necessidade de rastreabilidade entre unidade analisada e fonte.
- **Deng, Schlichtkrull e Vlachos (2024):** utilizam o documento completo como entrada e preservam o documento de origem durante seleção de sentenças, geração de contexto e decontextualização.

Adaptação para o projeto:

| Conceito nas referências | Aplicação no projeto |
|---|---|
| Documento de origem | Vídeo e transcript |
| Identidade da fonte | URL e `video_id` |
| Sentença de origem | Trecho do transcript e timestamp |
| Evidência rastreável | `source_text` ligado ao vídeo |

Os artigos não fornecem um protocolo específico para coleta de vídeos do YouTube. Portanto, a catalogação proposta é uma adaptação operacional dos princípios de proveniência, rastreabilidade e preservação do documento de origem.

### 4.3 Input

Input mínimo:

```json
{
  "youtube_url": "https://www.youtube.com/watch?v=VIDEO_ID"
}
```

Input enriquecido opcional:

```json
{
  "youtube_url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "search_query": "Ozempic emagrecimento",
  "selection_reason": "Vídeo em português com alegações sobre semaglutida"
}
```

### 4.4 Step 1.1 — Verificar elegibilidade

Critérios iniciais:

- conteúdo relacionado a semaglutida ou medicamentos GLP-1;
- idioma incluído no escopo do estudo;
- presença de conteúdo verbal;
- vídeo acessível no momento da coleta;
- duração dentro do limite definido;
- ausência de duplicidade no corpus;
- transcript disponível ou possibilidade de transcrição.

Output intermediário para inclusão:

```json
{
  "eligible": true,
  "exclusion_reason": null
}
```

Output intermediário para exclusão:

```json
{
  "eligible": false,
  "exclusion_reason": "DUPLICATE_VIDEO"
}
```

### 4.5 Step 1.2 — Definir identificador persistente

O identificador original do YouTube deve ser preservado mesmo que o título ou a forma da URL sejam alterados.

```json
{
  "video_id": "abc123xyz",
  "youtube_url": "https://www.youtube.com/watch?v=abc123xyz"
}
```

Relacionamentos futuros:

```text
video_id
   ├── transcript
   ├── transcript segments
   ├── claim spans
   └── atomic claims
```

### 4.6 Step 1.3 — Capturar metadados da fonte

| Campo | Descrição |
|---|---|
| `video_id` | Identificador original do vídeo |
| `youtube_url` | URL da fonte |
| `title` | Título observado durante a coleta |
| `channel_id` | Identificador do canal |
| `channel_name` | Nome observado do canal |
| `published_at` | Data de publicação |
| `duration_seconds` | Duração do vídeo |
| `language` | Idioma identificado |
| `collected_at` | Data e hora da coleta |
| `selection_reason` | Justificativa da inclusão |
| `source_status` | Estado do vídeo durante a coleta |

Valores propostos para `source_status`:

```text
AVAILABLE
UNAVAILABLE
PRIVATE
REMOVED
RESTRICTED
```

### 4.7 Step 1.4 — Preservar uma versão observável da fonte

Como o vídeo, o título e a descrição podem ser alterados ou removidos, devem ser preservados:

- metadados observados;
- descrição do vídeo;
- data e hora da coleta;
- thumbnail, quando relevante;
- arquivo de vídeo ou áudio, quando permitido;
- hash do arquivo coletado, quando houver cópia local.

```json
{
  "collected_at": "2026-09-26T14:30:00-03:00",
  "media_sha256": "HASH_DO_ARQUIVO",
  "source_status": "AVAILABLE"
}
```

O hash serve para verificar a identidade dos bytes coletados. Ele não avalia a veracidade do conteúdo.

### 4.8 Step 1.5 — Validar o registro

Fluxo de validação:

```text
URL válida?
   ↓ sim
video_id identificado?
   ↓ sim
vídeo elegível?
   ↓ sim
metadados mínimos presentes?
   ↓ sim
fonte registrada
```

Validações mínimas:

```text
video_id != null
youtube_url != null
collected_at != null
source_status == AVAILABLE
eligible == true
duplicate_of == null
```

### 4.9 Output — `VideoSourceRecord`

```json
{
  "video_id": "abc123xyz",
  "youtube_url": "https://www.youtube.com/watch?v=abc123xyz",
  "title": "Ozempic emagrece? Entenda como funciona",
  "channel_id": "UC123456",
  "channel_name": "Canal Exemplo",
  "published_at": "2026-01-15",
  "duration_seconds": 742,
  "language": "pt-BR",
  "collected_at": "2026-09-26T14:30:00-03:00",
  "selection_reason": "Contém alegações sobre indicação, mecanismo e efeitos adversos da semaglutida",
  "source_status": "AVAILABLE",
  "eligible": true,
  "exclusion_reason": null,
  "duplicate_of": null,
  "media_sha256": null
}
```

Encadeamento:

```text
VideoSourceRecord
        ↓
Step 2 — Obtenção e alinhamento temporal do transcript
```

### 4.10 Critérios de aceite

- [ ] Cada vídeo possui um `video_id` único.
- [ ] A URL original foi preservada.
- [ ] Os critérios de inclusão e exclusão foram aplicados.
- [ ] Os metadados mínimos foram registrados.
- [ ] A data e a hora da coleta foram armazenadas.
- [ ] Vídeos duplicados foram identificados.
- [ ] O registro permite ligar os futuros claims à fonte original.
- [ ] Nenhum claim foi extraído ou classificado nesta etapa.
- [ ] Step 1 aprovado pelo pesquisador.

---

## 5. Decisões metodológicas consolidadas

1. Claim Extraction será tratada separadamente de Claim Classification e Claim Verification.
2. A Pipeline V1 será apresentada de forma enxuta; os detalhes técnicos ficarão no workflow step by step.
3. O workflow seguirá divide and conquer, com aprovação humana entre as etapas.
4. Cada etapa terá input, metodologia/técnica, outputs intermediários, output final e critérios de aceite.
5. Todo claim deverá manter vínculo com vídeo, timestamp e texto de origem.
6. O Step 1 é uma etapa de proveniência e catalogação, não de extração de claims.
7. O próximo avanço depende do **OK no Step 1**.

---

## 6. Conceitos fundamentais

### Claim

Afirmação que expressa uma proposição potencialmente verificável.

### Claim Extraction

Processo de identificar e estruturar as afirmações verificáveis presentes em um texto, sem decidir se são verdadeiras ou falsas.

### Claim Dataset

Conjunto estruturado de claims extraídos, mantendo cada claim ligado ao trecho e à fonte que o originaram.

### Claim Span

Trecho específico do texto que contém uma afirmação relevante.

### Claim atômico

Claim que contém apenas uma proposição factual principal.

### Context Window

Conjunto de sentenças próximas usado para interpretar referências e recuperar informações necessárias ao entendimento do trecho.

### Claim Normalization

Transformação de linguagem ruidosa ou coloquial em uma formulação mais clara, preservando o significado da fonte.

### Decontextualization

Transformação de uma afirmação dependente do contexto em uma afirmação compreensível isoladamente, sem adicionar conhecimento externo.

### Faithfulness

Avalia se o claim representa corretamente aquilo que foi afirmado na fonte. Não avalia se a afirmação é verdadeira.

### Provenance

Capacidade de rastrear um claim até o vídeo, timestamp e texto de origem.

---

## 7. Referências

**Thorne, J., Vlachos, A., Christodoulopoulos, C., & Mittal, A. (2018).**  
*FEVER: a Large-scale Dataset for Fact Extraction and VERification.*  
NAACL-HLT 2018. DOI: `10.18653/v1/N18-1074`.

**Choi, E., Palomaki, J., Lamm, M., Kwiatkowski, T., Das, D., & Collins, M. (2021).**  
*Decontextualization: Making Sentences Stand-Alone.*  
Transactions of the Association for Computational Linguistics. DOI: `10.1162/tacl_a_00377`.

**Sundriyal, M., Kulkarni, A., Pulastya, V., Akhtar, M. S., & Chakraborty, T. (2022).**  
*Empowering the Fact-checkers! Automatic Identification of Claim Spans on Twitter.*  
EMNLP 2022. DOI: `10.18653/v1/2022.emnlp-main.525`.

**Min, S., et al. (2023).**  
*FActScore: Fine-grained Atomic Evaluation of Factual Precision in Long Form Text Generation.*  
EMNLP 2023. DOI: `10.18653/v1/2023.emnlp-main.741`.

**Sundriyal, M., Chakraborty, T., & Nakov, P. (2023).**  
*From Chaos to Clarity: Claim Normalization to Empower Fact-Checking.*  
Findings of EMNLP 2023. DOI: `10.18653/v1/2023.findings-emnlp.439`.

**Mittal, S., Sundriyal, M., & Nakov, P. (2023).**  
*Lost in Translation, Found in Spans: Identifying Claims in Multilingual Social Media.*  
EMNLP 2023. DOI: `10.18653/v1/2023.emnlp-main.236`.

**Deng, Z., Schlichtkrull, M., & Vlachos, A. (2024).**  
*Document-level Claim Extraction and Decontextualisation for Fact-Checking.*  
ACL 2024. DOI: `10.18653/v1/2024.acl-long.645`.

**Ullrich, H., Mlynář, T., & Drchal, J. (2025).**  
*Claim Extraction for Fact-Checking: Data, Models, and Automated Metrics.*  
arXiv: `2502.04955`. Dataset: **FEVERFact**.

---

## 8. Próximo passo

Revisar os critérios, campos e limites do Step 1. Após o pesquisador registrar **OK no Step 1**, detalhar:

> **Step 2 — Obtenção e alinhamento temporal do transcript**

