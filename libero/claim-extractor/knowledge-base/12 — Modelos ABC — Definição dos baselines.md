# PhD — Claim Extractor: Resumo do Chat

## 1. Objetivo

Simplificar o projeto para usar **uma única pipeline conceitual de Claim Extraction**, executada de forma generativa por LLMs, em vez de usar modelos especializados diferentes para cada etapa.

A pipeline lógica definida é:

```text
Claim Span Identification
→ Atomic Claim Decomposition
→ Claim Normalization
→ Decontextualization
```

O resultado final da pipeline é um **Claim Dataset** contendo claims atômicos, fiéis ao texto-fonte, normalizados e autocontidos.

---

## 2. Mudança metodológica principal

O projeto passa a seguir uma abordagem **2025+ de Claim Extraction generativa end-to-end**.

Em vez de:

```text
CSI → BERT/RoBERTa
Atomic → outro modelo
Normalization → T5/BART
Decontextualization → T5
```

a proposta é:

```text
Transcript
   ↓
LLM Claim Extractor
   ↓
executa logicamente:
CSI → Atomic → Normalization → Decontextualization
   ↓
Claim Dataset
```

As etapas continuam existindo como **especificação lógica da tarefa**, mas não precisam ser implementadas por modelos NLP separados.

---

## 3. Metodologia de benchmark

O desenho experimental segue a lógica do FEVERFact:

```text
mesmo dataset
    ↓
mesma tarefa de Claim Extraction
    ↓
diferentes modelos
    ↓
mesmo framework de métricas
```

Para tornar a comparação controlada, devem ser mantidos fixos, sempre que possível:

- dataset;
- splits;
- prompt/instruções;
- contexto fornecido;
- output schema;
- parâmetros de inferência;
- estratégia de few-shot;
- framework de avaliação.

A principal variável experimental será o **modelo**.

### Benchmark vs. Ablation Study

Se a pipeline permanece a mesma e apenas o modelo muda, o estudo é melhor descrito como:

- **Model Benchmark**;
- **Comparative Model Evaluation**;
- **Claim Extraction Model Benchmark**.

Não é propriamente um ablation study.

Ablation seria, por exemplo:

```text
CSI → Atomic → Normalization → Decontextualization
```

versus:

```text
CSI → Atomic → Decontextualization
```

removendo deliberadamente um componente.

---

## 4. Métricas de qualidade dos claims

O framework principal de avaliação será baseado em métricas intrínsecas de qualidade de Claim Extraction:

- **Atomicity**
- **Faithfulness**
- **Decontextualization**
- **Fluency**
- **Focus**
- **Coverage**
- **F_fact**
- **Redundancy**

Organização conceitual:

```text
Claim-level
├── Atomicity
├── Faithfulness
├── Decontextualization
└── Fluency

Claim-set level
├── Focus
├── Coverage
├── F_fact
└── Redundancy
```

`F_fact` representa o equilíbrio entre **Focus** e **Coverage**.

Importante: **Faithfulness** mede se o claim preserva corretamente a afirmação da fonte. Não mede se a afirmação é verdadeira no mundo.

---

## 5. Artigos científicos de referência

### FEVER — Thorne et al. (2018)

**FEVER: a Large-scale Dataset for Fact Extraction and VERification**

DOI: `10.18653/v1/N18-1074`

Uso principal no projeto:

- fact verification;
- evidence retrieval;
- provenance;
- estrutura de datasets para fact-checking.

Não é um Claim Extractor generativo moderno.

Modelos/arquiteturas históricos utilizados incluem retrieval baseado em TF-IDF/DrQA e modelos de textual entailment.

---

### Choi et al. (2021)

**Decontextualization: Making Sentences Stand-Alone**

DOI: `10.1162/tacl_a_00377`

Uso principal:

- decontextualization.

Modelos avaliados incluíram:

- coreference baselines;
- T5-Base;
- T5-11B.

Referência importante para definir o objetivo de transformar uma afirmação em sentença autocontida.

---

### Sundriyal et al. (2022)

**Empowering the Fact-checkers! Automatic Identification of Claim Spans on Twitter**

DOI: `10.18653/v1/2022.emnlp-main.525`

Uso principal:

- Claim Span Identification.

Modelos incluem:

- BERT;
- RoBERTa;
- SpanBERT;
- CRF;
- DABERTa.

Representa a abordagem anterior baseada em modelos especializados por etapa.

---

### Min et al. (2023)

**FActScore: Fine-grained Atomic Evaluation of Factual Precision in Long Form Text Generation**

DOI: `10.18653/v1/2023.emnlp-main.741`

Uso principal:

- Atomic Claim / Atomic Fact Decomposition.

O trabalho utiliza prompting com LLM para decompor texto em fatos atômicos.

É uma referência central para o conceito de atomicidade.

---

### Sundriyal et al. (2023)

**From Chaos to Clarity: Claim Normalization to Empower Fact-Checking**

DOI: `10.18653/v1/2023.findings-emnlp.439`

Uso principal:

- Claim Normalization.

Pontos importantes:

- **CLAN** é o dataset;
- **CACN** é o método/modelo;
- foram avaliados T5, BART, FLAN-T5, PEGASUS e GPT-3.

Cuidado metodológico:

CACN usa check-worthiness e priorização de claims potencialmente falsos/relevantes, o que pode introduzir viés em um pipeline que deseja extrair **todos os claims**, inclusive verdadeiros, falsos, enganosos e não suportados.

---

### Mittal et al. (2023)

**Lost in Translation, Found in Spans: Identifying Claims in Multilingual Social Media**

DOI: `10.18653/v1/2023.emnlp-main.236`

Uso principal:

- multilingual Claim Span Identification.

Modelos incluem:

- mBERT;
- mDeBERTa;
- XLM-R.

Útil como referência multilíngue, mas não valida diretamente português brasileiro.

---

### Deng et al. (2024)

**Document-level Claim Extraction and Decontextualisation for Fact-Checking**

DOI: `10.18653/v1/2024.acl-long.645`

Uso principal:

- composição de Claim Extraction + Decontextualization em nível documental.

Utiliza modelos como:

- BERT/BertSum;
- DeBERTa;
- BART;
- T5;
- retrieval/QA.

É o precedente mais próximo de uma pipeline composta, embora ainda anterior ao foco moderno em um único LLM generativo.

---

### Ullrich et al. (2025) — FEVERFact

**Claim Extraction for Fact-Checking: Data, Models, and Automated Metrics**

arXiv: `2502.04955`

Dataset: **FEVERFact**

É uma das referências centrais do projeto.

O paper compara diferentes estratégias/modelos de Claim Extraction usando o mesmo dataset e o mesmo framework de métricas.

Modelos incluem:

- QACG;
- GPT-4 Turbo;
- Mistral-7B-Instruct-v0.2 + QLoRA;
- T5 em diferentes estratégias de geração.

O **Mistral-7B-Instruct-v0.2 + QLoRA** apresentou o melhor equilíbrio de Focus/Coverage entre os modelos avaliados no benchmark reportado, tornando-se um excelente baseline científico.

---

### Claimify — ACL 2025

**Towards Effective Extraction and Evaluation of Factual Claims**

Referência muito relevante para a metodologia atual.

O Claimify trata Claim Extraction como tarefa generativa baseada em LLM e compara a mesma estratégia com diferentes modelos-base.

Foram utilizados, entre outros:

- GPT-4o;
- Mistral Large;
- DeepSeek-V3.

Esse desenho é muito próximo do benchmark desejado:

```text
mesmo método
+
diferentes LLMs
+
mesma avaliação
```

---

### Fadda et al. (2026)

Trabalho recente em Claim Extraction de notícias com múltiplos LLMs.

Foi utilizado como evidência complementar para observar o desempenho de modelos modernos como:

- Kimi-K2;
- DeepSeek-V3.1;
- GLM;
- Qwen;
- Llama;
- gpt-oss.

Os resultados não devem ser comparados diretamente com FEVERFact porque datasets e métricas são diferentes.

---

## 6. Arquitetura experimental com três modelos

Foi decidido utilizar três categorias de modelo:

```text
Model A
Scientific baseline
        ↓
Model B
Community specialized model
        ↓
Model C
Domain-specific custom model
```

Todos executam a **mesma tarefa de Claim Extraction generativa**.

---

## 7. Modelo A — baseline científico

Proposta:

```text
Mistral-7B-Instruct-v0.2
+
QLoRA
```

Justificativa:

- utilizado no FEVERFact;
- evidência publicada;
- configuração de treinamento documentada;
- avaliado diretamente com métricas relevantes ao projeto;
- open-weight;
- reproduzível.

Papel metodológico:

> **Literature-backed Claim Extraction baseline**

O objetivo do Modelo A não é necessariamente representar o modelo mais moderno disponível, mas fornecer uma âncora científica replicável.

---

## 8. Modelo B — community specialized Claim Extractor

Candidato principal:

```text
principled-intelligence/
claim-extractor-4B-q-2605
```

Base:

```text
Qwen3.5-4B
```

Características:

- modelo da comunidade;
- especializado em Claim Extraction;
- foco em claims atômicos e decontextualizados;
- saída estruturada;
- tamanho pequeno o suficiente para experimentação em GPU de consumo;
- útil como comparação entre evidência científica formal e especialização da comunidade.

Papel metodológico:

> **Community-developed specialized Claim Extraction model**

### Alternativa

```text
Luimas/
claim-extractor-detective-qwen3b
```

Base:

```text
Qwen2.5-3B
```

Características:

- QLoRA;
- JSON estruturado;
- claims atômicos;
- evidence spans.

Limitação relevante:

- explicitamente English-only.

Por isso, fica como candidato secundário.

---

## 9. LangChain e LangGraph

LangChain e LangGraph **não são modelos**.

Eles devem ser tratados como infraestrutura/orquestração.

Exemplo:

```text
Transcript
    ↓
LangGraph
    ↓
Claim Extractor LLM
    ↓
Structured Output
    ↓
Schema Validation
    ↓
Claim Dataset
```

Podem ser utilizados para:

- workflow;
- retries;
- structured output;
- Pydantic/JSON validation;
- logging;
- observabilidade;
- execução das etapas lógicas do pipeline.

Mas não devem aparecer na tese como “Modelo B”.

---

## 10. Modelo C — modelo customizado para o projeto

Proposta inicial:

```text
Qwen3-8B
+
QLoRA / SFT
```

Objetivo:

criar um Claim Extractor específico para:

- GLP-1;
- semaglutida/Ozempic;
- transcripts de vídeos;
- linguagem informal;
- português;
- estrutura de claims desejada pelo projeto.

Pipeline aprendida:

```text
Claim Span Identification
→ Atomic Claim Decomposition
→ Claim Normalization
→ Decontextualization
```

O Modelo C representa a contribuição experimental específica do projeto.

Papel metodológico:

> **Domain-specific custom Claim Extraction model**

---

## 11. Interpretação dos três modelos

A estrutura fica:

```text
A = scientific evidence

B = community specialization

C = domain specialization
```

Visualmente:

```text
                  MODEL A
           SCIENTIFIC BASELINE
                  │
                  ▼
       Mistral-7B + QLoRA
           FEVERFact

                  MODEL B
       COMMUNITY SPECIALIST
                  │
                  ▼
       ClaimExtractor-4B
        Qwen3.5-4B base

                  MODEL C
         DOMAIN SPECIALIST
                  │
                  ▼
         Qwen3-8B + QLoRA
       GLP-1 video transcripts
```

---

## 12. Dataset e splits

O dataset deve ser dividido em:

```text
Golden / Annotated Dataset
        │
        ├── Train
        │     ↓
        │   Model C
        │
        ├── Validation
        │     ↓
        │   hyperparameters
        │   model selection
        │
        └── Test
              ↓
          A vs B vs C
```

Regra central:

**O test set não pode ser utilizado no treinamento ou fine-tuning do Modelo C.**

Também deve ser evitado usar o test set para repetidas decisões de prompt/model selection.

---

## 13. Comparação final

```text
                   HELD-OUT TEST SET
                          │
              ┌───────────┼───────────┐
              │           │           │
              ▼           ▼           ▼
           Model A     Model B     Model C
              │           │           │
              ▼           ▼           ▼
           Claims A     Claims B     Claims C
              │           │           │
              └───────────┼───────────┘
                          ▼
                SAME EVALUATION FRAMEWORK
                          │
              Atomicity
              Faithfulness
              Decontextualization
              Fluency
              Focus
              Coverage
              F_fact
              Redundancy
```

---

## 14. Pergunta experimental possível

Uma formulação possível:

> **How does a literature-validated Claim Extraction model compare with a community-specialized Claim Extraction model and a domain-specific fine-tuned model for extracting high-quality claims from GLP-1 video transcripts?**

---

## 15. Próximos passos

1. Validar definitivamente o **Modelo A** e reproduzir a configuração do FEVERFact.
2. Instalar e testar o **ClaimExtractor-4B-q-2605** como Modelo B.
3. Definir o schema definitivo de output para todos os modelos.
4. Criar um pequeno **development set** com anotação humana.
5. Definir o protocolo de prompt comum.
6. Implementar o framework de métricas.
7. Criar Train / Validation / Test sem vazamento.
8. Preparar o dataset de treinamento do Modelo C.
9. Comparar alternativas de SFT, LoRA e QLoRA para o Modelo C.
10. Executar o benchmark final A vs B vs C no mesmo held-out test set.

---

## 16. Decisão metodológica consolidada

A metodologia atual do projeto pode ser resumida como:

```text
ONE GENERATIVE CLAIM EXTRACTION TASK

Claim Span Identification
→ Atomic Claim Decomposition
→ Claim Normalization
→ Decontextualization

                ↓

THREE MODEL STRATEGIES

A = Scientific baseline
B = Community specialized model
C = Domain-specific fine-tuned model

                ↓

SAME HELD-OUT DATASET
SAME OUTPUT SCHEMA
SAME EVALUATION FRAMEWORK

                ↓

Atomicity
Faithfulness
Decontextualization
Fluency
Focus
Coverage
F_fact
Redundancy
```

Essa estrutura preserva a fundamentação científica, incorpora modelos modernos da comunidade e abre espaço para uma contribuição original via adaptação ao domínio GLP-1.
