# PhD — Claim Extractor: Benchmark dos Modelos A, B e C

## 1. Objetivo

O projeto de doutorado investiga desinformação sobre GLP-1 (por exemplo, semaglutida/Ozempic) em vídeos de YouTube/TikTok.

Esta fase é focada exclusivamente em **Claim Extraction**, isto é, transformar transcripts em claims:

- atômicos;
- fiéis ao texto-fonte;
- claros;
- decontextualizados;
- pouco redundantes;
- adequados para posterior fact-checking.

A etapa de **Claim Verification / Veracity Classification** fica fora deste benchmark.

Pergunta principal:

> Qual dos Modelos A, B e C produz claims de maior qualidade intrínseca quando aplicado ao mesmo conjunto de transcripts held-out?

---

## 2. Pipeline de Claim Extraction

Pipeline conceitual fixa:

```text
YouTube Video
      ↓
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

### Claim Span Identification

Identifica trechos do transcript que contêm afirmações factual/verificáveis.

Referências principais:

- Sundriyal et al. (2022)
- Mittal et al. (2023)

### Atomic Claim Decomposition

Divide sentenças compostas em proposições independentes.

Exemplo:

```text
"Ozempic reduz o apetite e pode causar náusea."
```

torna-se:

```text
C001 — Ozempic reduz o apetite.
C002 — Ozempic pode causar náusea.
```

Referência principal:

- Min et al. (2023), FActScore

### Claim Normalization

Converte linguagem falada/coloquial em uma formulação factual mais clara, preservando o significado original.

Referência principal:

- Sundriyal, Chakraborty & Nakov (2023)

### Decontextualization

Torna cada claim compreensível isoladamente.

Exemplo:

```text
"Ela reduz o apetite."
```

torna-se:

```text
"Semaglutida reduz o apetite."
```

Referências principais:

- Choi et al. (2021)
- Deng et al. (2024)
- Claimify (ACL 2025)

---

## 3. Modelos do benchmark

### Model A — Scientific Baseline

Candidato principal:

```text
Mistral-7B-Instruct-v0.2
+
FEVERFact / QLoRA-style adaptation
```

Papel:

- baseline científico;
- modelo baseado diretamente em literatura de Claim Extraction;
- referência reproduzível para comparação.

Referência principal:

- Ullrich et al. (2025), FEVERFact.

---

### Model B — Community Specialized Claim Extractor

Candidato principal:

```text
principled-intelligence/claim-extractor-4B-q-2605
```

Backbone:

```text
Qwen3.5-4B
```

Papel:

- representar um open-model da comunidade já especializado em Claim Extraction.

Características relevantes:

- atomic claims;
- decontextualization;
- structured output;
- foco em fact-checking.

---

### Community model complementar

Também poderá ser testado:

```text
Luimas/claim-extractor-detective-qwen3b
```

Características:

- Qwen2.5-3B;
- QLoRA;
- teacher Qwen2.5-14B;
- JSON estruturado;
- atomic claims;
- evidence spans;
- scripts/corpus/benchmarks disponíveis;
- Apache 2.0;
- English-only.

Uso recomendado:

```text
Community Model Screening

B1 — claim-extractor-4B-q-2605
B2 — claim-extractor-detective-qwen3b
```

O modelo `detective-qwen3b` não deve ser excluído apenas por ser English-only, mas seu resultado precisa ser interpretado separadamente em PT-BR.

---

### Model C — GLP-1 Domain Adapted

Modelo customizado para o domínio do projeto.

Estratégia preferencial:

```text
Community Claim Extractor
        ↓
SFT / QLoRA
        ↓
GLP-1 Claim Extraction Dataset
        ↓
MODEL C
```

Idealmente, B e C compartilham a mesma linhagem/backbone:

```text
B = Qwen3.5-4B Claim Extractor
C = mesmo checkpoint/backbone + fine-tuning GLP-1
```

Assim, a comparação:

```text
B vs C
```

mede de forma mais controlada o efeito da adaptação ao domínio GLP-1.

---

## 4. Literatura recente considerada

### Claimify — ACL 2025

Claimify é uma **metodologia/framework de Claim Extraction**, não um modelo específico.

O trabalho avalia Claim Extraction usando diferentes LLMs e foca especialmente em:

- Entailment;
- Element-level Coverage;
- Decontextualization;
- ambiguity handling;
- decomposition;
- claims orientados a fact-checking.

Claimify reforça a separação entre:

```text
Claim Extraction methodology
        ↓
underlying LLM
```

---

### Fadda et al. — Knowledge-Based Systems 2026

O trabalho propõe uma arquitetura multi-agent para Claim Extraction.

Estrutura conceitual:

```text
Article
   ↓
multiple LLM extractors
   ↓
aggregator LLM
   ↓
final claims
```

A implementação utiliza LangGraph como camada de orquestração.

Implicação para o projeto:

- reforça a comparação de múltiplos LLMs;
- mostra o potencial de ensembles;
- mas ensemble não deve ser misturado inicialmente no benchmark A/B/C, pois adicionaria outra variável experimental.

Experimento futuro possível:

```text
best single model
vs
multi-model ensemble
```

---

## 5. Framework de avaliação final

Pipeline/metodologia adotada:

```text
                 HELD-OUT TRANSCRIPTS
                         │
             ┌───────────┼───────────┐
             ↓           ↓           ↓
          MODEL A     MODEL B     MODEL C
             │           │           │
             └───────────┼───────────┘
                         ↓
                 GENERATED CLAIMS
                         │
          ┌──────────────┴──────────────┐
          ↓                             ↓

       FEVERFact                     Claimify
          │                             │
     Atomicity                      Entailment
     Faithfulness                   Element Coverage
     Fluency                        Decontextualization
     Focus
     Coverage
     F_fact
     Redundancy
          │                             │
          └──────────────┬──────────────┘
                         ↓
                Human Validation
                         ↓
                 A vs B vs C
```

---

## 6. Métricas FEVERFact

### Atomicity

Pergunta:

> O claim contém uma única proposição factual principal?

Direção:

```text
↑ melhor
```

---

### Faithfulness

Pergunta:

> O claim preserva o que foi efetivamente afirmado no transcript?

Importante:

> Faithfulness não mede verdade médica.

Um claim pode ser fiel ao transcript e ainda ser cientificamente falso.

Direção:

```text
↑ melhor
```

---

### Fluency

Avalia clareza, correção gramatical e inteligibilidade do claim.

Direção:

```text
↑ melhor
```

---

### Focus

Mede quanto do conjunto gerado corresponde a informação relevante.

Conceitualmente semelhante a Precision.

Direção:

```text
↑ melhor
```

---

### Coverage

Mede quanto da informação factual relevante foi recuperada.

Conceitualmente semelhante a Recall.

Direção:

```text
↑ melhor
```

---

### F_fact

Média harmônica entre Focus e Coverage:

```text
F_fact = 2 × Focus × Coverage
         --------------------
           Focus + Coverage
```

Será uma das principais métricas agregadas do benchmark.

Direção:

```text
↑ melhor
```

---

### Redundancy

Avalia repetição semântica entre claims.

Direção:

```text
↓ melhor
```

---

## 7. Métricas Claimify

### Entailment

Pergunta:

> O claim é realmente implicado pelo texto-fonte?

Ajuda a detectar:

- hallucinations;
- inferências não presentes no transcript;
- conteúdo não sustentado pela fonte.

Direção:

```text
↑ melhor
```

---

### Element Coverage

Mede quantos elementos factuais verificáveis presentes na fonte foram capturados pelo conjunto de claims.

Especialmente útil para transcripts com múltiplas proposições por sentença.

Direção:

```text
↑ melhor
```

---

### Decontextualization

Pergunta:

> O claim pode ser interpretado corretamente sem consultar novamente o restante do transcript?

Direção:

```text
↑ melhor
```

---

## 8. Scorecard final

| Métrica | Framework | Direção |
|---|---|---:|
| Atomicity | FEVERFact | ↑ |
| Faithfulness | FEVERFact | ↑ |
| Fluency | FEVERFact | ↑ |
| Focus | FEVERFact | ↑ |
| Coverage | FEVERFact | ↑ |
| F_fact | FEVERFact | ↑ |
| Redundancy | FEVERFact | ↓ |
| Entailment | Claimify | ↑ |
| Element Coverage | Claimify | ↑ |
| Decontextualization | Claimify | ↑ |

---

## 9. Human Validation

A avaliação automática será validada com anotação humana em uma amostra do test set.

Isto é importante porque o corpus contém:

- português brasileiro;
- linguagem falada;
- transcripts de vídeo;
- termos médicos;
- conteúdo GLP-1;
- linguagem informal/social media.

Dimensões sugeridas:

- Atomicity;
- Faithfulness;
- Entailment;
- Decontextualization;
- Fluency;
- Coverage.

Possíveis métricas de concordância:

- Gwet's AC1;
- Krippendorff's alpha;
- agreement percentual.

---

## 10. Dataset e splits

Divisão recomendada:

```text
GOLD DATASET
     ↓
┌───────────┬───────────┬───────────┐
│           │           │           │
Train       Dev         Test
│           │           │
Model C     tuning      A/B/C
training                benchmark
```

O held-out test set não pode ser usado para:

- treinamento;
- seleção de checkpoint;
- tuning de hiperparâmetros;
- prompt tuning.

---

## 11. Gold Claims

Estrutura mínima sugerida:

```text
transcript_id
claim_id
source_text
claim
```

Opcional:

```text
start_timestamp
end_timestamp
source_span
annotator_id
```

O Gold Claim Dataset representa:

> quais claims deveriam ser extraídos daquele transcript.

---

## 12. Protocolo experimental

Todos os modelos devem receber:

- os mesmos held-out transcripts;
- o mesmo chunking;
- o mesmo contexto;
- o mesmo schema de saída;
- a mesma definição funcional de Claim Extraction;
- o mesmo limite de geração;
- parâmetros determinísticos quando possível.

Preferencialmente:

```text
temperature = 0
```

---

## 13. Agregação dos resultados

Preferência:

```text
macro-average por transcript
```

Também reportar:

- média;
- mediana;
- intervalo de confiança de 95%;
- distribuição por transcript.

---

## 14. Comparação estatística

Como A/B/C são avaliados nos mesmos transcripts, a comparação é pareada.

Opções:

```text
paired bootstrap
```

e, quando apropriado:

```text
Friedman test
    ↓
post-hoc pairwise
    ↓
Holm correction
```

---

## 15. Perguntas de pesquisa

### RQ1

Como o baseline científico baseado em FEVERFact se comporta em transcripts sobre GLP-1?

```text
Model A
```

### RQ2

Um open-model comunitário especializado em Claim Extraction supera o baseline científico?

```text
A vs B
```

### RQ3

A adaptação específica ao domínio GLP-1 melhora a qualidade da extração?

```text
B vs C
```

---

## 16. Critério de seleção final

O melhor modelo não será escolhido apenas contando quantas métricas venceu.

A decisão deverá considerar conjuntamente:

- F_fact;
- Element Coverage;
- Entailment;
- Faithfulness;
- Atomicity;
- Decontextualization;
- Fluency;
- Redundancy;
- intervalos de confiança;
- consistência com avaliação humana;
- reprodutibilidade.

Objetivo:

```text
boa cobertura
+
baixo ruído
+
alta fidelidade
+
claims atômicos
+
claims autocontidos
+
baixa redundância
```

---

## 17. Fora do escopo

Não usar nesta fase:

- Accuracy de veracity classification;
- Precision/Recall/F1 de misinformation classification;
- Confusion Matrix;
- Calibration;
- harmfulness score.

Essas métricas pertencem às etapas futuras de Claim Classification e Claim Verification.

---

## 18. Referências principais

- Thorne et al. (2018) — FEVER
- Choi et al. (2021) — Decontextualization
- Sundriyal et al. (2022) — Claim Span Identification
- Min et al. (2023) — FActScore
- Sundriyal et al. (2023) — Claim Normalization / CACN
- Mittal et al. (2023) — Multilingual Claim Spans
- Deng et al. (2024) — Document-level Claim Extraction and Decontextualisation
- Ullrich et al. (2025) — FEVERFact
- Metropolitansky & Larson (2025) — Claimify
- Fadda et al. (2026) — Multi-agent Claim Extraction

---

## 19. Título sugerido para este chat

**PhD — Claim Extractor: Pipeline, Modelos A/B/C e Métricas**
