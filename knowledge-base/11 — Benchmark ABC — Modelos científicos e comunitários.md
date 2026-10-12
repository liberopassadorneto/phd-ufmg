# PhD — Claim Extractor: Pipeline, Modelos A/B/C e Benchmark

## 1. Objetivo do projeto

O projeto de doutorado investiga **Claim Extraction** a partir de transcrições de vídeos, especialmente conteúdos relacionados a GLP-1, semaglutida e Ozempic.

O objetivo desta etapa é transformar transcrições brutas em um conjunto estruturado de claims que possam ser avaliados posteriormente quanto à qualidade intrínseca da extração e, em etapas futuras, quanto à veracidade, harmfulness e outras dimensões.

A prioridade atual é **avaliar a qualidade do Claim Extractor de forma independente da classificação downstream**.

---

## 2. Pipeline fixa de Claim Extraction

Foi definida uma única pipeline conceitual:

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

### Etapas

1. **Claim Span Identification (CSI)**  
   Identifica trechos do transcript que contêm afirmações verificáveis ou factuais.

2. **Atomic Claim Decomposition**  
   Divide afirmações compostas em claims atômicos, idealmente contendo uma única proposição verificável.

3. **Claim Normalization**  
   Reescreve o claim para uma forma mais clara e padronizada, preservando seu significado original.

4. **Decontextualization**  
   Torna o claim autossuficiente, adicionando contexto mínimo necessário sem alterar seu conteúdo semântico.

---

## 3. Metodologia de benchmark

A metodologia segue a filosofia do **FEVERFact**:

```text
MESMO DATASET
    ↓
DIFERENTES MODELOS DE CLAIM EXTRACTION
    ↓
MESMO FRAMEWORK DE MÉTRICAS
```

O objetivo não é comparar diferentes pipelines, mas diferentes modelos/implementações executando a mesma tarefa de Claim Extraction.

Assim, a variável principal do experimento será:

```text
MODEL
```

e não:

```text
MODEL + pipeline + prompt + training strategy + contexto
```

Sempre que possível, devem ser mantidos constantes:

- transcripts;
- splits;
- contexto fornecido;
- prompt/instruções;
- output schema;
- parâmetros de decoding;
- preprocessing;
- framework de avaliação.

---

## 4. Benchmark vs. Ablation Study

Uma distinção metodológica importante:

### Benchmark / Comparative Model Evaluation

Se a pipeline permanece fixa e apenas o modelo muda:

```text
Model A
vs
Model B
vs
Model C
```

isso é um **benchmark de modelos** ou **comparative model evaluation**.

### Ablation Study

Uma ablation ocorreria se um componente fosse removido ou alterado, por exemplo:

```text
CSI → Atomic → Decontext
```

versus:

```text
CSI → Atomic → Normalization → Decontext
```

Como o projeto foi simplificado para uma única pipeline fixa, o experimento principal será tratado como **benchmark**, não como ablation study.

---

## 5. Métricas intrínsecas de qualidade

As métricas principais seguem o FEVERFact:

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

### Claim-level

- **Atomicity**  
  Mede se cada claim contém uma única proposição verificável.

- **Faithfulness**  
  Mede se o claim preserva aquilo que foi realmente afirmado no transcript.

  Importante: faithfulness não mede veracidade factual. Um claim falso pode estar perfeitamente faithful ao transcript.

- **Decontextualization**  
  Mede se o claim pode ser compreendido isoladamente.

- **Fluency**  
  Mede qualidade linguística, clareza e legibilidade.

### Claim-set level

- **Focus**  
  Mede o quanto os claims gerados correspondem adequadamente às proposições relevantes.

- **Coverage**  
  Mede quanto do conteúdo factual relevante do input foi coberto.

- **F_fact**  
  Média harmônica entre Focus e Coverage.

- **Redundancy**  
  Mede repetição ou sobreposição excessiva entre claims.

Observação: Redundancy deve ser tratada com cautela, pois no FEVERFact sua validação humana é menos consolidada do que a das demais métricas.

---

## 6. Artigos científicos de referência e modelos utilizados

### FEVER — Thorne et al. (2018)

**FEVER: a Large-scale Dataset for Fact Extraction and VERification**  
DOI: `10.18653/v1/N18-1074`

Não é um Claim Extractor modular. Os claims foram produzidos por humanos.

Componentes de baseline:

- DrQA / TF-IDF para evidence retrieval;
- Decomposable Attention para textual entailment.

Relevância para o projeto:

- claim/evidence;
- provenance;
- verificação factual;
- desenho de datasets.

---

### Choi et al. (2021)

**Decontextualization: Making Sentences Stand-Alone**  
DOI: `10.1162/tacl_a_00377`

Modelos:

- SpanBERT-Large;
- T5-Base;
- T5-11B.

T5-11B apresentou os melhores resultados automáticos entre os modelos testados.

Relevância:

- fundamentação científica para Decontextualization.

---

### Sundriyal et al. (2022)

**Empowering the Fact-checkers! Automatic Identification of Claim Spans on Twitter**  
DOI: `10.18653/v1/2022.emnlp-main.525`

Modelos/arquiteturas:

- CNN/BiLSTM + CRF;
- DistilBERT;
- BERT;
- SpanBERT;
- RoBERTa;
- DABERTa.

O método proposto **DABERTa**, baseado em RoBERTa com adapters, foi desenvolvido para Claim Span Identification.

Relevância:

- fundamentação científica para CSI.

---

### Min et al. (2023)

**FActScore: Fine-grained Atomic Evaluation of Factual Precision in Long Form Text Generation**  
DOI: `10.18653/v1/2023.emnlp-main.741`

Uso principal:

- decomposição de texto em atomic facts.

Modelo original:

- InstructGPT / `text-davinci-003`.

Relevância:

- metodologia de Atomic Claim Decomposition;
- atomic facts como unidade de avaliação.

Limitação:

- modelo original proprietário.

---

### Sundriyal et al. (2023)

**From Chaos to Clarity: Claim Normalization to Empower Fact-Checking**  
DOI: `10.18653/v1/2023.findings-emnlp.439`

Conceitos:

- **CLAN** = dataset;
- **CACN** = método de Claim Normalization.

Modelos/baselines:

- T5 Base/Large;
- BART Base/Large;
- FLAN-T5 Base/Large;
- PEGASUS;
- GPT-3 / `text-davinci-003`.

CACN utiliza:

- GPT-3;
- chain-of-thought;
- in-context examples;
- check-worthiness.

Relevância:

- fundamentação para Claim Normalization.

Cuidado metodológico:

CACN prioriza check-worthy claims. Para este projeto, a normalização deve preferencialmente ser **neutral e meaning-preserving**, evitando introduzir viés de falsidade ou relevância antes da verificação.

---

### Mittal et al. (2023)

**Lost in Translation, Found in Spans: Identifying Claims in Multilingual Social Media**  
DOI: `10.18653/v1/2023.emnlp-main.236`

Modelos:

- mBERT;
- mDeBERTa;
- XLM-R;
- GPTs via prompting.

Relevância:

- CSI multilíngue;
- comparação entre encoders multilingual e LLMs.

Limitação:

- português não fazia parte do benchmark principal.

---

### Deng et al. (2024)

**Document-level Claim Extraction and Decontextualisation for Fact-Checking**  
DOI: `10.18653/v1/2024.acl-long.645`

Componentes:

- BERT/BertSum;
- DocNLI;
- BM25;
- QA;
- BART para QA2D;
- T5 para decontextualization;
- DeBERTa para check-worthiness.

Relevância:

- precedente de pipeline composta de Claim Extraction + Decontextualization.

---

### FENICE — Scirè, Ghonim & Navigli (2024)

**FENICE: Factuality Evaluation of Summarization based on Natural Language Inference and Claim Extraction**

Modelo especializado:

- FLAN-T5-base fine-tuned para Claim Extraction.

Modelo público:

```text
Babelscape/t5-base-summarization-claim-extractor
```

Características:

- ~200M parâmetros;
- extrai atomic claims;
- possui avaliação acadêmica;
- desempenho próximo de GPT-3.5 em benchmark reportado.

Limitações:

- English-only;
- treinado principalmente para summaries;
- domínio diferente de transcripts.

---

### Ullrich, Mlynář & Drchal (2025)

**Claim Extraction for Fact-Checking: Data, Models, and Automated Metrics**  
arXiv: `2502.04955`

Dataset:

- **FEVERFact**

Modelos comparados:

- QACG;
- GPT-4 Turbo 3-shot;
- Mistral-7B-Instruct-v0.2 + QLoRA;
- T5 multi-claim;
- T5 diverse beam.

Métricas:

- Atomicity;
- Fluency;
- Decontextualization;
- Faithfulness;
- Focus;
- Coverage;
- F_fact;
- Redundancy.

Resultado importante:

O **Mistral-7B-Instruct-v0.2 + QLoRA** apresentou o melhor equilíbrio entre Focus e Coverage dentre os modelos avaliados, alcançando o maior `F_fact` no benchmark apresentado.

Relevância:

- principal referência metodológica para o benchmark do projeto.

---

### Claimify — Metropolitansky & Larson (ACL 2025)

**Towards Effective Extraction and Evaluation of Factual Claims**

Claimify propõe uma metodologia de Claim Extraction com etapas como:

```text
Selection
   ↓
Disambiguation
   ↓
Decomposition
   ↓
Decontextualized claims
```

Modelos testados:

- GPT-4o;
- Mistral-Large;
- DeepSeek-V3.

Importância:

- demonstra diretamente que o mesmo método de Claim Extraction produz resultados diferentes dependendo do LLM usado;
- reforça o desenho experimental de manter método/pipeline fixa e variar modelos.

---

## 7. Modelos abertos da comunidade pesquisados

### Principled Intelligence — ClaimExtractor-4B-q-2605

Modelo:

```text
principled-intelligence/claim-extractor-4B-q-2605
```

Base:

- Qwen3.5-4B.

Objetivo:

```text
conversation
   ↓
atomic claims
   ↓
decontextualized claims
   ↓
structured output
```

Características:

- especializado em conversations;
- usa contexto de mensagens anteriores;
- gera claims self-contained;
- output estruturado;
- Apache 2.0;
- execução via Transformers, vLLM ou SGLang.

É um dos modelos comunitários mais alinhados ao contexto:

```text
video transcript
+
context window
→ atomic/decontextualized claims
```

Limitação:

- ainda não possui o mesmo nível de validação peer-reviewed do FEVERFact ou Claimify.

---

### ClaimExtractor-2B-q-2605

Variante menor:

```text
principled-intelligence/claim-extractor-2B-q-2605
```

Base:

- Qwen3.5-2B.

Objetivo:

- mesmo do modelo 4B;
- menor custo e uso de memória.

Pode ser útil para testes de infraestrutura ou comparação de eficiência.

---

### Luimas — claim-extractor-detective-qwen3b

Modelo:

```text
Luimas/claim-extractor-detective-qwen3b
```

Base:

- Qwen2.5-3B-Instruct;
- QLoRA;
- distillation a partir de Qwen2.5-14B.

Output:

- atomic claims;
- claim type;
- stance;
- sentiment;
- verbatim evidence;
- verification questions;
- contradictions;
- JSON estruturado.

Pontos fortes:

- voltado a misinformation/fact-checking;
- inclui evidence anchoring;
- possui scripts de benchmark e evaluation;
- Apache 2.0;
- versões GGUF disponíveis.

Limitação principal:

- English-only.

---

### SAGESSE-EPFL — Mistral-7B Claims Extraction

Modelo:

```text
SAGESSE-EPFL/Mistral-7b-claims-extraction
```

Base:

- Mistral-7B-Instruct-v0.3;
- LoRA.

Input:

```text
Submission
+
Parent Comment
+
Current Comment
```

Output:

- claims self-contained;
- contexto incorporado ao claim.

É estruturalmente semelhante a:

```text
video context
+
previous transcript
+
current transcript segment
→ claims
```

Limitações:

- dataset político/Reddit;
- generalização para domínio médico ainda não demonstrada;
- evidência científica inferior aos modelos publicados em papers consolidados.

---

## 8. Definição dos três modelos do benchmark

O projeto adotará três categorias de modelos.

---

### Modelo A — baseline científico

Objetivo:

> Representar uma abordagem já validada em literatura científica de Claim Extraction.

Candidato principal:

```text
Mistral-7B-Instruct-v0.2
+
QLoRA
+
FEVERFact
```

Motivação:

- utilizado em paper diretamente focado em Claim Extraction;
- validado com métricas compatíveis com o projeto;
- resultados disponíveis;
- reproduzível;
- representa o baseline científico.

---

### Modelo B — baseline da comunidade

Objetivo:

> Representar um open-model especializado em Claim Extraction criado pela comunidade.

Candidato principal:

```text
principled-intelligence/
claim-extractor-4B-q-2605
```

Base:

```text
Qwen3.5-4B
```

Motivação:

- explicitamente treinado para conversation → claims;
- atomic claims;
- decontextualization;
- structured output;
- open-weight;
- execução local;
- domínio estrutural próximo a transcript + context.

Outros candidatos exploratórios:

```text
Luimas/claim-extractor-detective-qwen3b

SAGESSE-EPFL/Mistral-7b-claims-extraction
```

---

### Modelo C — modelo customizado do projeto

Objetivo:

> Criar um Claim Extractor adaptado especificamente a transcripts de vídeos sobre GLP-1.

Estratégia preferida:

```text
open-weight base model
      ↓
domain/project dataset
      ↓
SFT
+
LoRA / QLoRA
      ↓
GLP1-ClaimExtractor
```

Uma possibilidade metodologicamente interessante é usar:

```text
Qwen3.5-4B
```

como base do Modelo C.

Isso permite uma comparação direta:

```text
MODEL B
Qwen3.5-4B
+
community Claim Extraction training
```

versus:

```text
MODEL C
Qwen3.5-4B
+
GLP-1/project-specific fine-tuning
```

Assim, B vs C mede mais claramente o efeito da adaptação ao domínio.

---

## 9. Arquitetura experimental A/B/C

```text
                    HELD-OUT TEST SET
                           │
                    SAME TRANSCRIPTS
                           │
                  SAME TASK CONTRACT
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
         ▼                 ▼                 ▼
     MODEL A           MODEL B           MODEL C

 Scientific          Community           Custom
 baseline             open model         GLP-1 model

 FEVERFact         ClaimExtractor       Qwen3.5-4B
 Mistral-7B          Qwen3.5-4B             +
   + QLoRA                              SFT/QLoRA

         │                 │                 │
         └─────────────────┼─────────────────┘
                           ▼
                   SAME EVALUATION
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

## 10. Perguntas científicas possibilitadas pelo benchmark

### A vs B

```text
scientific literature baseline
vs
community specialized Claim Extractor
```

Pergunta:

> Um modelo comunitário especializado em Claim Extraction consegue igualar ou superar uma abordagem validada cientificamente?

---

### B vs C

```text
generic/community Claim Extractor
vs
domain-adapted Claim Extractor
```

Pergunta:

> A adaptação para transcripts médicos/GLP-1 melhora a qualidade intrínseca dos claims?

---

### A vs C

```text
literature-established method
vs
project-specific method
```

Pergunta:

> O modelo desenvolvido no projeto melhora a qualidade de Claim Extraction em relação ao baseline científico?

---

## 11. Splits do dataset

O benchmark deve evitar data leakage.

Estrutura:

```text
Training set
    ↓
fine-tuning do Model C

Development / Validation set
    ↓
model selection
hyperparameters
prompt/schema tuning
early stopping

Held-out Test set
    ↓
final benchmark
A vs B vs C
```

O **held-out test set não deve ser usado para escolher modelos, prompts ou hiperparâmetros**.

---

## 12. Reprodutibilidade

Sempre que possível, manter fixos:

- transcript;
- segmentação;
- context window;
- prompt;
- output schema;
- temperature;
- decoding parameters;
- preprocessing;
- post-processing;
- métricas;
- versão do dataset.

Registrar:

```text
model_id
model_revision
prompt_version
dataset_version
seed
temperature
max_tokens
context_length
hardware
inference_backend
```

---

## 13. Português e domain shift

Existem diferenças importantes entre os datasets originais dos modelos e o domínio do projeto.

Os modelos pesquisados foram treinados principalmente em:

- Wikipedia;
- summaries;
- Twitter;
- Reddit;
- notícias;
- diálogos;
- inglês.

O projeto utiliza:

```text
raw video transcripts
+
ASR noise
+
spoken language
+
Portuguese / possibly mixed language
+
medical/pharmaceutical domain
```

Portanto, é necessário validar empiricamente:

- suporte a português;
- robustez a ASR;
- preservação de terminologia médica;
- manutenção de números/dosagens;
- coreference em spoken language;
- atomicidade;
- faithfulness.

Essa diferença de domínio é também uma forte justificativa científica para o **Modelo C**.

---

## 14. LangChain / LangGraph

LangChain e LangGraph não são modelos.

Eles podem ser utilizados como camada de infraestrutura:

```text
Transcript Loader
      ↓
Chunking / Context
      ↓
LangGraph workflow
      ↓
Model A / B / C
      ↓
Structured Output
      ↓
Evaluation
```

Seu papel pode incluir:

- orchestration;
- context management;
- retries;
- structured output validation;
- batch execution;
- experiment tracking.

A variável experimental continua sendo o **modelo de Claim Extraction**, não o framework de orquestração.

---

## 15. Direção consolidada

A versão simplificada do projeto fica:

```text
ONE CLAIM EXTRACTION TASK
            │
            ▼
      SAME TRANSCRIPTS
            │
            ▼
      SAME TASK CONTRACT
            │
       ┌────┼────┐
       ▼    ▼    ▼
       A    B    C
       │    │    │
       └────┼────┘
            ▼
     SAME METRICS
```

Com:

```text
A = scientific baseline
B = community open Claim Extractor
C = custom GLP-1 Claim Extractor
```

e métricas:

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

---

## 16. Referências principais

### Dataset / Fact-checking

Thorne, J., Vlachos, A., Christodoulopoulos, C., & Mittal, A. (2018).  
**FEVER: a Large-scale Dataset for Fact Extraction and VERification.**  
NAACL-HLT 2018.  
DOI: `10.18653/v1/N18-1074`

### Decontextualization

Choi, E., Palomaki, J., Lamm, M., Kwiatkowski, T., Das, D., & Collins, M. (2021).  
**Decontextualization: Making Sentences Stand-Alone.**  
Transactions of the Association for Computational Linguistics.  
DOI: `10.1162/tacl_a_00377`

### Claim Span Identification

Sundriyal, M., Kulkarni, A., Pulastya, V., Akhtar, M. S., & Chakraborty, T. (2022).  
**Empowering the Fact-checkers! Automatic Identification of Claim Spans on Twitter.**  
EMNLP 2022.  
DOI: `10.18653/v1/2022.emnlp-main.525`

### Atomic Facts

Min, S., et al. (2023).  
**FActScore: Fine-grained Atomic Evaluation of Factual Precision in Long Form Text Generation.**  
EMNLP 2023.  
DOI: `10.18653/v1/2023.emnlp-main.741`

### Claim Normalization

Sundriyal, M., Chakraborty, T., & Nakov, P. (2023).  
**From Chaos to Clarity: Claim Normalization to Empower Fact-Checking.**  
Findings of EMNLP 2023.  
DOI: `10.18653/v1/2023.findings-emnlp.439`

### Multilingual Claim Spans

Mittal, S., Sundriyal, M., & Nakov, P. (2023).  
**Lost in Translation, Found in Spans: Identifying Claims in Multilingual Social Media.**  
EMNLP 2023.  
DOI: `10.18653/v1/2023.emnlp-main.236`

### Document-level Claim Extraction

Deng, Z., Schlichtkrull, M., & Vlachos, A. (2024).  
**Document-level Claim Extraction and Decontextualisation for Fact-Checking.**  
ACL 2024.  
DOI: `10.18653/v1/2024.acl-long.645`

### FENICE

Scirè, A., Ghonim, A., & Navigli, R. (2024).  
**FENICE: Factuality Evaluation of Summarization based on Natural Language Inference and Claim Extraction.**  
Findings of ACL 2024.

### FEVERFact

Ullrich, H., Mlynář, T., & Drchal, J. (2025).  
**Claim Extraction for Fact-Checking: Data, Models, and Automated Metrics.**  
arXiv: `2502.04955`

### Claimify

Metropolitansky, D., & Larson, M. (2025).  
**Towards Effective Extraction and Evaluation of Factual Claims.**  
ACL 2025.

---

## 17. Próximos passos

1. Congelar o contrato da tarefa de Claim Extraction.
2. Definir schema final do output.
3. Validar disponibilidade e execução local do Modelo A.
4. Testar o Modelo B com transcripts reais.
5. Criar pequeno development set anotado manualmente.
6. Definir dataset de treinamento do Modelo C.
7. Escolher estratégia de SFT/LoRA/QLoRA.
8. Executar model screening.
9. Congelar A/B/C.
10. Executar benchmark final no held-out test set.
