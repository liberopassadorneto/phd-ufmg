# PhD — Claim Extractor: Pipeline, Component Benchmark & Ablation Study

## 1. Objetivo do projeto

O projeto de doutorado busca construir uma pipeline de **Claim Extraction** para transcrições de vídeos, com foco posterior em desinformação sobre GLP-1/semaglutida.

O objetivo atual é transformar transcrições brutas em um **CLAIM DATASET** de alta qualidade, antes de avançar para classificação de veracidade, harmfulness ou outras tarefas downstream.

Pipeline conceitual atual:

```text
Transcript
   ↓
Claim Span Identification
   ↓
Atomic Claim Decomposition
   ↓
Claim Normalization
   ↓
Decontextualization
   ↓
CLAIM DATASET
```

A classificação factual ainda não faz parte deste experimento.

## 2. FEVERFact vs. pipeline modular

O trabalho de **Ullrich et al. (2025) / FEVERFact** não implementa explicitamente uma pipeline como:

```text
CSI → Atomic → Normalization → Decontextualization
```

A estratégia principal é **end-to-end Claim Extraction**:

```text
Contextualized document
        ↓
Claim Extraction model
        ↓
Generated claims
        ↓
Intrinsic quality evaluation
```

Os autores comparam diferentes modelos/estratégias de geração. Atomicity e Decontextualization aparecem principalmente como **propriedades esperadas dos claims e métricas de avaliação**, e não como etapas explícitas e independentes da pipeline.

## 3. Métricas de qualidade do FEVERFact

### Per-claim
- **Atomicity**
- **Faithfulness**
- **Decontextualization**
- **Fluency**

### Set-level
- **Focus**
- **Coverage**
- **F_fact**
- **Redundancy**

Essas métricas são apropriadas para avaliar a qualidade do Claim Extractor antes de qualquer classificador de veracidade.

## 4. Estratégias encontradas nos artigos científicos

### Thorne et al. (2018) — FEVER
Objetivo principal: criação e verificação de claims.

```text
Wikipedia sentence
    ↓
Human claim generation / modification
    ↓
Claim
    ↓
Evidence retrieval
    ↓
Verification
```

Não implementa uma pipeline modular de Claim Extraction.

### Choi et al. (2021) — Decontextualization

```text
Sentence + Context
        ↓
Decontextualization
        ↓
Stand-alone sentence
```

O melhor sistema automático estudado foi baseado em **T5-11B**. É a principal referência para o componente de Decontextualization.

### Sundriyal et al. (2022) — Claim Span Identification

```text
Social-media post
        ↓
Claim Span Identification
        ↓
Claim span
```

O método proposto é **DABERTa**, baseado em RoBERTa + adapters.

### Min et al. (2023) — FActScore

```text
Long-form text
        ↓
Sentence splitting
        ↓
Atomic Fact Decomposition
        ↓
Atomic facts
        ↓
Factual support evaluation
```

A decomposição em fatos atômicos foi realizada com **InstructGPT / text-davinci-003**. A contribuição mais relevante para o projeto é a metodologia de **Atomic Fact Decomposition**, e não necessariamente o modelo específico.

### Sundriyal et al. (2023) — ClaimNorm

```text
Complex / noisy social-media post
        ↓
Claim Normalization
        ↓
Normalized claim
```

Ponto importante:

```text
CLAN = dataset
CACN = método/modelo
```

**CACN — Check-worthiness Aware Claim Normalization** foi o método proposto e apresentou melhores resultados do que os baselines avaliados no próprio paper.

Porém, CACN pode introduzir **selection bias**, pois incorpora check-worthiness. Para um Claim Dataset que deve preservar claims verdadeiros, falsos, misleading e unsupported, uma forma de **neutral normalization** pode ser mais adequada.

### Mittal et al. (2023) — Multilingual Claim Span Identification

Expande Claim Span Identification para contexto multilíngue. Modelos avaliados incluem XLM-R, mDeBERTa e mBERT, além de estratégias de zero-shot e tradução.

### Deng et al. (2024) — Document-level Claim Extraction and Decontextualisation

É o trabalho mais próximo de uma pipeline composta:

```text
Document
   ↓
Central Sentence Selection
   ↓
QA-based context construction
   ↓
Decontextualization
   ↓
Claim
```

Demonstra precedente científico para uma **composed claim-extraction pipeline**, embora não use CSI → Atomic → Norm → Decontext.

### Ullrich et al. (2025) — FEVERFact

Compara diferentes Claim Extractors e estratégias de geração usando o mesmo framework de avaliação. Não realiza explicitamente:

```text
Atomic → Normalization → Decontextualization
```

nem uma ablação controlada adicionando/removendo apenas Claim Normalization.

## 5. Interpretação metodológica

Os trabalhos existentes podem ser agrupados em três tipos:

### Subtask papers
```text
CSI
Atomic Decomposition
Claim Normalization
Decontextualization
```

### Composed pipelines
Exemplo principal:

```text
Deng et al. 2024

Central Sentence Selection
        ↓
Decontextualization
```

### Claim Extraction benchmarks
Exemplo:

```text
FEVERFact

different extractors
        ↓
same evaluation framework
```

## 6. Controlled Component Ablation Study

O nome metodológico mais adequado para o experimento planejado é:

**Controlled Component Ablation Study**

ou:

**Controlled Ablation Experiment**

Experimento:

```text
same transcripts
same model
same inference settings
same context
same evaluation

A:
CSI → Atomic → Decontext

B:
CSI → Atomic → Normalization → Decontext
```

A única variável experimental deve ser a presença de **Claim Normalization**.

Pergunta de pesquisa:

> What is the incremental effect of Claim Normalization on the intrinsic quality of atomic claims extracted from video transcripts?

## 7. O que precisa acontecer antes da ablação

Antes de executar a ablação, é necessário escolher e congelar a implementação de cada componente.

Devemos distinguir:

```text
Technique
Implementation / Algorithm
Model
```

Exemplo:

```text
Technique: Atomic Claim Decomposition
Implementation: FActScore-style decomposition
Model: selected instruction LLM
```

## 8. Candidatos atuais por componente

### Claim Span Identification
Candidatos fundamentados na literatura:
- DABERTa
- XLM-R
- mDeBERTa
- mBERT

Para português, XLM-R ou mDeBERTa podem ser candidatos mais adequados do que DABERTa, mas precisam ser validados no domínio-alvo.

### Atomic Claim Decomposition
Candidato metodológico:
- **FActScore-style Atomic Fact Decomposition**

O algoritmo/prompt pode ser reutilizado com um LLM open-weight moderno.

### Claim Normalization
Candidatos:
- **CACN**
- uma versão de **neutral normalization**

CACN não deve ser tratado automaticamente como “melhor algoritmo universal”; ele foi o melhor entre os métodos avaliados no contexto do ClaimNorm.

### Decontextualization
Candidatos:
- **Choi-style T5 decontextualization**
- **Deng-style QA context + T5 decontextualization**

Para transcripts longos, a abordagem de Deng é particularmente relevante.

## 9. Domain shift

Os melhores métodos dos papers não podem ser assumidos automaticamente como os melhores para transcripts de GLP-1.

```text
CSI:
Twitter → YouTube transcripts

Atomic:
LLM-generated biographies → spoken medical claims

Normalization:
social-media posts → long-form transcript

Decontextualization:
Wikipedia / documents → spoken video transcript
```

Portanto, os métodos publicados devem ser tratados como **literature-backed candidates**, não como soluções definitivamente superiores para o domínio-alvo.

## 10. Próxima etapa experimental

### Etapa 1 — Component Implementation Benchmark

```text
CSI       → qual implementação/modelo?
Atomic    → qual implementação/modelo?
Norm      → qual implementação/modelo?
Decontext → qual implementação/modelo?
```

Exemplos:

```text
CSI:
DABERTa
vs
XLM-R

Atomic:
FActScore-style + Model X
vs
FActScore-style + Model Y

Normalization:
CACN
vs
Neutral Normalization

Decontextualization:
Choi T5
vs
Deng QA-context + T5
```

### Etapa 2 — Freeze da Pipeline

```text
CSI       = selected implementation
Atomic    = selected implementation
Norm      = selected implementation
Decontext = selected implementation
```

### Etapa 3 — Controlled Component Ablation

```text
A:
CSI → Atomic → Decontext

B:
CSI → Atomic → Norm → Decontext
```

Avaliar com:

```text
Atomicity
Faithfulness
Decontextualization
Fluency
Focus
Coverage
F_fact
Redundancy
```

## 11. Principal conclusão

A literatura já oferece:

- técnicas cientificamente avaliadas para CSI, Atomic Decomposition, Normalization e Decontextualization;
- algoritmos e modelos candidatos para implementar essas técnicas;
- métricas intrínsecas para avaliar a qualidade dos claims.

Porém, os papers analisados não apresentam exatamente uma pipeline:

```text
CSI → Atomic → Normalization → Decontextualization
```

nem um experimento controlado:

```text
CSI → Atomic → Decontext
vs
CSI → Atomic → Norm → Decontext
```

mantendo os demais fatores constantes.

Antes dessa ablação, a prioridade metodológica é realizar um **Component Implementation Benchmark** para selecionar e congelar a melhor implementação de cada etapa no domínio de transcripts de vídeos sobre GLP-1.

## 12. Referências principais

- Thorne, J., Vlachos, A., Christodoulopoulos, C., & Mittal, A. (2018). *FEVER: a Large-scale Dataset for Fact Extraction and VERification*. NAACL-HLT 2018. DOI: `10.18653/v1/N18-1074`
- Choi, E., Palomaki, J., Lamm, M., Kwiatkowski, T., Das, D., & Collins, M. (2021). *Decontextualization: Making Sentences Stand-Alone*. TACL. DOI: `10.1162/tacl_a_00377`
- Sundriyal, M., Kulkarni, A., Pulastya, V., Akhtar, M. S., & Chakraborty, T. (2022). *Empowering the Fact-checkers! Automatic Identification of Claim Spans on Twitter*. EMNLP 2022. DOI: `10.18653/v1/2022.emnlp-main.525`
- Min, S. et al. (2023). *FActScore: Fine-grained Atomic Evaluation of Factual Precision in Long Form Text Generation*. EMNLP 2023. DOI: `10.18653/v1/2023.emnlp-main.741`
- Sundriyal, M., Chakraborty, T., & Nakov, P. (2023). *From Chaos to Clarity: Claim Normalization to Empower Fact-Checking*. Findings of EMNLP 2023. DOI: `10.18653/v1/2023.findings-emnlp.439`
- Mittal, S., Sundriyal, M., & Nakov, P. (2023). *Lost in Translation, Found in Spans: Identifying Claims in Multilingual Social Media*. EMNLP 2023. DOI: `10.18653/v1/2023.emnlp-main.236`
- Deng, X., Schlichtkrull, M., & Vlachos, A. (2024). *Document-level Claim Extraction and Decontextualisation for Fact-Checking*. ACL 2024. DOI: `10.18653/v1/2024.acl-long.645`
- Ullrich, H., Mlynář, T., & Drchal, J. (2025). *Claim Extraction for Fact-Checking: Data, Models, and Automated Metrics*. arXiv:2502.04955.
