# PhD — Golden Dataset e Classificação de Misinformation sobre GLP-1 com LLMs

## Objetivo deste chat

Este chat consolidou a metodologia para estruturar um projeto de classificação de desinformação sobre GLP-1/semaglutida a partir de transcrições de vídeos.

A ideia central é separar o problema em duas grandes etapas:

```text
TRANSCRIÇÃO
   ↓
EXTRAÇÃO / ORGANIZAÇÃO EM CLAIMS
   ↓
CLASSIFICAÇÃO DE CADA CLAIM
```

Depois, os claims anotados por especialistas formam um **Gold-Standard Dataset**, que pode ser dividido em treino, validação e teste para fine-tuning e avaliação de uma LLM.

---

# 1. O que é um claim?

Um **claim** é uma afirmação factual verificável sobre o mundo.

Exemplo:

> “Ozempic reduz o apetite.”

Esse conteúdo pode ser confrontado com evidência científica e classificado.

Já frases como:

> “Na minha opinião, Ozempic mudou minha vida.”

são opiniões e não deveriam necessariamente receber labels de veracidade como `TRUE` ou `FALSE`.

## Tipos iniciais de conteúdo

Antes da classificação de veracidade, a transcrição pode ser organizada em tipos:

```text
FACTUAL_MEDICAL_CLAIM
PERSONAL_EXPERIENCE
OPINION
QUESTION
ADVERTISEMENT
NON_MEDICAL_STATEMENT
```

Somente os `FACTUAL_MEDICAL_CLAIM` seguem obrigatoriamente para fact-checking.

---

# 2. Atomic Claim Decomposition

Um claim deve ser o mais **atômico** possível, isto é, conter idealmente uma única proposição verificável.

Exemplo inadequado:

```text
“Semaglutida reduz o apetite e causa náusea.”
```

Esse trecho contém dois claims:

```text
C1 = Semaglutida reduz o apetite.
C2 = Semaglutida causa náusea.
```

Isso é importante porque cada claim pode receber um label diferente.

Outro exemplo:

```text
“Ozempic não causa pancreatite e pode ser usado durante a gravidez.”
```

Deve ser decomposto em:

```text
C1 = Ozempic não causa pancreatite.
C2 = Ozempic pode ser usado durante a gravidez.
```

---

# 3. Preciso estruturar o transcript em claims antes de classificar?

Sim.

Para este projeto, a estratégia mais robusta é:

```text
VIDEO
  ↓
TRANSCRIPTION
  ↓
CLAIM SPAN IDENTIFICATION
  ↓
ATOMIC CLAIM DECOMPOSITION
  ↓
CLAIM NORMALIZATION
  ↓
DECONTEXTUALIZATION
  ↓
CLAIM TYPE
  ↓
FACTUAL MEDICAL CLAIM?
  ↓
EVIDENCE RETRIEVAL
  ↓
VERACITY CLASSIFICATION
```

Isso evita atribuir um único label de “verdadeiro” ou “falso” a um vídeo inteiro que pode conter informação correta e incorreta simultaneamente.

---

# 4. Golden Dataset

O **Golden Dataset** é o conjunto de exemplos anotados por humanos/especialistas de acordo com um protocolo definido.

Estrutura recomendada:

```text
GOLD-STANDARD DATASET
        ↓
       SPLIT
        ↓
┌───────────────┬────────────────┬───────────────┐
↓               ↓                ↓
TRAIN           VALIDATION       TEST
70–80%          10–15%           10–15%
↓               ↓                ↓
fine-tune       model selection  final evaluation
```

## Uso dos splits

### Training Set

É utilizado para fazer o fine-tuning e alterar os pesos do modelo.

### Validation Set

É usado durante o desenvolvimento para:

```text
seleção de hiperparâmetros
early stopping
escolha de checkpoint
LoRA rank
learning rate
número de epochs
prompt/template
thresholds
```

Não deve ser tratado como dado de treino normal.

### Test Set

Deve permanecer congelado até o final.

Ele mede a capacidade real de generalização do modelo.

---

# 5. O Golden Dataset inteiro é usado no fine-tuning?

Não.

Somente o `training split` deve participar diretamente do fine-tuning.

Correto:

```text
Golden Dataset
      ↓
split
      ↓
Training Set
      ↓
fine-tune
```

Incorreto:

```text
Golden Dataset inteiro
      ↓
fine-tune
      ↓
avaliar no mesmo conjunto
```

Esse segundo desenho produz **data leakage** e métricas artificialmente elevadas.

---

# 6. Label não é necessariamente um score

É importante separar:

```text
LABEL
SCORE
EVIDENCE
```

## Label categórico

Exemplo:

```text
ACCURATE
MISLEADING
FALSE
INSUFFICIENT_EVIDENCE
```

O especialista escolhe uma categoria.

## Scores auxiliares

Podem representar:

```text
harmfulness
evidence_strength
annotator_confidence
quality
completeness
```

Exemplo:

```json
{
  "veracity": "FALSE",
  "harmfulness": 4,
  "evidence_strength": 5,
  "annotator_confidence": 5
}
```

---

# 7. Como o especialista conclui se o claim é verdadeiro ou não?

A decisão não deve depender somente de opinião ou conhecimento pessoal.

O processo ideal é:

```text
CLAIM
  ↓
É verificável?
  ↓
SIM
  ↓
BUSCAR EVIDÊNCIA
  ↓
comparar CLAIM × EVIDÊNCIA
  ↓
aplicar regras do annotation guideline
  ↓
atribuir LABEL
```

A relação entre claim e evidência pode ser modelada como:

```text
SUPPORTS
CONTRADICTS
INSUFFICIENT
```

E convertida em:

```text
SUPPORTS      → ACCURATE
CONTRADICTS   → FALSE
PARCIAL       → MISLEADING
INSUFFICIENT  → INSUFFICIENT_EVIDENCE
```

---

# 8. Proposta de labels de veracidade

## ACCURATE

A evidência científica relevante sustenta substancialmente o claim e não há distorção material.

## FALSE

Evidência confiável contradiz diretamente o claim.

## MISLEADING

O claim contém elementos verdadeiros, mas produz uma interpretação clinicamente equivocada por:

```text
exagero
omissão
generalização
contexto inadequado
causalidade indevida
minimização de risco
```

## INSUFFICIENT_EVIDENCE

Não existe evidência de qualidade suficiente para sustentar nem refutar adequadamente a afirmação.

## NON_VERIFIABLE

Pode ser utilizado antes da classificação de veracidade para:

```text
opiniões
perguntas
experiências pessoais
slogans
afirmações não factuais
```

---

# 9. Estrutura hierárquica recomendada

Em vez de criar um único label complexo, separar as dimensões:

```text
1. CLAIM TYPE
   FACTUAL_MEDICAL_CLAIM
   PERSONAL_EXPERIENCE
   OPINION
   QUESTION
   etc.

2. VERACITY
   ACCURATE
   MISLEADING
   FALSE
   INSUFFICIENT_EVIDENCE

3. MEDICAL TOPIC
   INDICATION
   DOSAGE
   EFFICACY
   MECHANISM
   ADVERSE_EFFECT
   CONTRAINDICATION
   DRUG_INTERACTION
   OFF_LABEL
   etc.

4. MISINFORMATION TYPE
   FACTUAL_ERROR
   EXAGGERATION
   OMISSION
   CONTEXT_DISTORTION
   ANECDOTAL_GENERALIZATION
   CAUSAL_OVERCLAIM
   RISK_MINIMIZATION
   MECHANISM_ERROR
   etc.

5. SCORES
   harmfulness
   evidence_strength
   annotator_confidence
```

---

# 10. Exemplo de anotação

Transcrição:

> “Ozempic é originalmente um remédio para diabetes. Ele elimina gordura diretamente e não tem efeitos colaterais importantes.”

Após atomização:

```text
C001 = Ozempic é usado no tratamento do diabetes tipo 2.
C002 = Semaglutida promove perda de peso eliminando diretamente gordura corporal.
C003 = Semaglutida não apresenta efeitos adversos importantes.
```

Exemplo de saída:

```json
[
  {
    "claim_id": "C001",
    "claim": "Ozempic é usado no tratamento do diabetes tipo 2.",
    "claim_type": "FACTUAL_MEDICAL_CLAIM",
    "topic": "INDICATION",
    "veracity": "ACCURATE"
  },
  {
    "claim_id": "C002",
    "claim": "Semaglutida promove perda de peso eliminando diretamente gordura corporal.",
    "claim_type": "FACTUAL_MEDICAL_CLAIM",
    "topic": "MECHANISM",
    "veracity": "FALSE",
    "misinformation_type": "MECHANISM_ERROR"
  },
  {
    "claim_id": "C003",
    "claim": "Semaglutida não apresenta efeitos adversos importantes.",
    "claim_type": "FACTUAL_MEDICAL_CLAIM",
    "topic": "ADVERSE_EFFECT",
    "veracity": "MISLEADING",
    "misinformation_type": "RISK_MINIMIZATION"
  }
]
```

---

# 11. Evidência no Golden Dataset

O Golden Dataset ideal não deveria armazenar apenas:

```text
claim | label
```

É preferível armazenar:

```text
claim
label
evidence
source
evidence_stance
rationale
evidence_strength
annotator_confidence
```

Exemplo:

```json
{
  "claim": "Semaglutida não apresenta efeitos gastrointestinais.",
  "veracity": "FALSE",
  "evidence_stance": "CONTRADICTS",
  "evidence_sources": [
    "FDA Prescribing Information",
    "STEP clinical trials"
  ],
  "rationale": "Eventos gastrointestinais como náusea, vômito e diarreia são documentados.",
  "evidence_strength": 5,
  "annotator_confidence": 5
}
```

---

# 12. Fontes de evidência recomendadas

Para GLP-1/semaglutida:

```text
FDA
EMA
ANVISA
bulas oficiais
guidelines clínicas
RCTs
ensaios STEP
systematic reviews
meta-analyses
peer-reviewed clinical studies
```

O objetivo é evitar que o especialista classifique somente com base em opinião individual.

---

# 13. Múltiplos especialistas

Idealmente, a criação do gold label utiliza mais de um anotador:

```text
                    CLAIM
                      │
          ┌───────────┼───────────┐
          ↓           ↓           ↓
       EXPERT A    EXPERT B    EXPERT C
          │           │           │
          └───────────┼───────────┘
                      ↓
               independent labels
                      ↓
               disagreement?
                 /         \
               yes          no
                ↓            ↓
           adjudication      │
                └──────┬─────┘
                       ↓
                   GOLD LABEL
```

Antes da adjudicação deve-se medir concordância entre anotadores.

Possíveis métricas:

```text
Cohen's κ
Fleiss' κ
Krippendorff's α
```

---

# 14. Artigos GLP-1 discutidos e uso de ground truth

## Propfe & Seifert — Misrepresentation of semaglutide in social media

- 250 posts em múltiplas plataformas.
- Avaliação manual de informações sobre indicação, mecanismo, efeitos adversos etc.
- Claims incorretos foram confrontados com literatura científica.
- Não construiu Golden Dataset para treinamento de IA.
- Útil como precedente para:
  - taxonomia GLP-1
  - comparação claim × evidência científica

Classificação:

```text
Human annotation: SIM
ML Golden Dataset: NÃO
```

---

## Yeung et al. — Online Information About Side Effects and Safety Concerns of Semaglutide

- Avaliação humana por dois reviewers.
- Uso de:
  - GQS
  - mDISCERN
  - checklist específico de semaglutida
- Divergências resolvidas por discussão.

Classificação:

```text
Human annotated corpus: SIM
Consensus: SIM
Golden Dataset para ML: NÃO
```

---

## Campos-Rivera et al.

- Avaliação manual de vídeos TikTok.
- DISCERN e análise de normas sociais/narrativa.
- Não há pipeline de IA comparada com gold labels.

Classificação:

```text
Manual content analysis: SIM
ML Golden Dataset: NÃO
```

---

## Sönmez & Fidanci

Importante precedente metodológico.

- Dois avaliadores independentes.
- Etapa de calibração com vídeos piloto.
- Scientific accuracy comparada com:
  - guidelines de obesidade
  - FDA-approved indications
  - principais clinical trials de semaglutida
- Cohen's κ = 0.81.

Classificação:

```text
Expert reference annotations: SIM
Calibration: SIM
External evidence: SIM
Inter-rater agreement: SIM
ML Golden Dataset: NÃO
```

É um dos melhores modelos metodológicos para a construção da anotação humana no presente projeto.

---

## Li et al.

- Dois reviewers.
- GQS, mDISCERN e JAMA.
- Calibração inicial.
- Consensus em casos de discordância.
- Cohen κ e ICC reportados.

Classificação:

```text
High-quality annotation process: SIM
Gold-standard-like annotation: SIM
ML Golden Dataset: NÃO
```

---

## Günaltay & Kartal

- DISCERN + JAMA + análise temática.
- Identificação de conteúdo misleading/risky.

Classificação:

```text
Manual evaluation: SIM
ML Golden Dataset: NÃO
```

---

## Peng et al.

- GQS
- mDISCERN
- JAMA
- content completeness

Classificação:

```text
Manual evaluation: SIM
ML Golden Dataset: NÃO
```

---

## Biçer & Biçer

Estudo metodologicamente muito próximo do objetivo.

- Dois médicos.
- Avaliação independente.
- Consenso.
- GQS, mDISCERN, JAMA.
- Medical Accuracy.
- Classificação final:
  - USEFUL
  - MISLEADING
- Claude Sonnet avaliou os mesmos vídeos sem acesso às avaliações humanas.

Classificação:

```text
Human reference standard: SIM
LLM vs human evaluation: SIM
Golden evaluation dataset: SIM, funcionalmente
Golden training dataset: NÃO
```

Limitações:

- preprint
- avaliação no nível do vídeo
- não claim-level
- não fine-tuning

---

## Somani et al.

- LLM/algoritmos usados para clustering e topic labeling.
- RoBERTa para sentiment.
- Não há grande conjunto humano de referência para misinformation.

Classificação:

```text
ML/LLM: SIM
Human misinformation ground truth: NÃO
```

---

## Javaid et al.

- BERTopic/BERT.
- RoBERTa para sentiment.
- Pequena validação qualitativa humana.

Classificação:

```text
Human qualitative validation: SIM
Golden Dataset: NÃO
```

---

## Sehgal et al.

É um dos exemplos mais próximos de ground truth para avaliação de IA.

- Manual annotation de subconjuntos de 100 posts.
- Comparação com classificadores LLM.
- Métricas de sensibilidade, especificidade, precision, recall e F1.

Classificação:

```text
Golden validation subsets: SIM
Large Golden Dataset for fine-tuning: NÃO
```

---

# 15. GQS, DISCERN e JAMA não são labels de veracidade

Esses instrumentos medem aspectos como:

```text
qualidade
reliability
completude
clareza
fontes
balanceamento
transparência
```

Eles não deveriam ser convertidos diretamente para:

```text
TRUE
FALSE
MISLEADING
```

Exemplo incorreto:

```text
GQS < 3 → misinformation
```

Isso mistura qualidade de apresentação com factualidade.

Uma informação pode ser:

```text
baixa qualidade de apresentação
mas factualmente correta
```

ou:

```text
alta qualidade visual
mas conter um claim falso
```

---

# 16. Gap metodológico identificado

Entre os artigos GLP-1 analisados, foram encontrados separadamente:

```text
claim/content analysis
human expert annotation
external scientific evidence
calibration
consensus
inter-rater agreement
LLM evaluation
```

Mas não foi identificado, entre os estudos discutidos, um pipeline completo como:

```text
TRANSCRIPT
  ↓
CLAIM EXTRACTION
  ↓
ATOMIC CLAIMS
  ↓
EXPERT + EVIDENCE VERIFICATION
  ↓
CLAIM-LEVEL VERACITY LABEL
  ↓
CONSENSUS
  ↓
GOLD-STANDARD DATASET
  ↓
TRAIN / VALIDATION / TEST
  ↓
FINE-TUNE LLM
  ↓
CLAIM-LEVEL MISINFORMATION CLASSIFICATION
```

Esse pode ser um dos principais diferenciais metodológicos do projeto.

---

# 17. Pipeline recomendada para o projeto

```text
VIDEOS
  ↓
TRANSCRIPTION
  ↓
CLAIM SPAN IDENTIFICATION
  ↓
ATOMIC CLAIM DECOMPOSITION
  ↓
CLAIM NORMALIZATION
  ↓
DECONTEXTUALIZATION
  ↓
CLAIM TYPE CLASSIFICATION
  ↓
FACTUAL MEDICAL CLAIM
  ↓
EVIDENCE RETRIEVAL
  ↓
FDA / EMA / ANVISA
RCTs
systematic reviews
meta-analyses
guidelines
  ↓
EXPERT A + EXPERT B (+ EXPERT C)
  ↓
INDEPENDENT ANNOTATION
  ↓
INTER-RATER AGREEMENT
  ↓
ADJUDICATION / CONSENSUS
  ↓
GOLD LABEL
  ↓
GOLD-STANDARD DATASET
  ↓
┌───────────┬────────────┬───────────┐
│ TRAIN     │ VALIDATION │ TEST      │
└───────────┴────────────┴───────────┘
      ↓
FINE-TUNE OPEN-WEIGHT LLM
      ↓
FINAL EVALUATION
```

---

# 18. Estrutura de dados candidata

```json
{
  "video_id": "VID001",
  "claim_id": "C003",
  "original_span": "...",
  "claim": "Semaglutida não apresenta efeitos adversos importantes.",
  "claim_type": "FACTUAL_MEDICAL_CLAIM",
  "topic": "ADVERSE_EFFECT",
  "veracity": "MISLEADING",
  "misinformation_type": "RISK_MINIMIZATION",
  "evidence_stance": "CONTRADICTS",
  "evidence_sources": [
    "FDA Prescribing Information",
    "STEP clinical trials"
  ],
  "evidence_strength": 5,
  "harmfulness": 4,
  "annotator_confidence": 5,
  "annotator_1": "MISLEADING",
  "annotator_2": "MISLEADING",
  "gold_label": "MISLEADING"
}
```

---

# 19. Decisões metodológicas consolidadas

1. A unidade principal de análise deve ser o **claim**, não o vídeo inteiro.
2. Claims devem ser decompostos em proposições atômicas.
3. Nem toda frase é um claim factual.
4. Veracidade deve ser tratada como label categórico.
5. Scores devem ficar em dimensões separadas.
6. A classificação humana deve ser baseada em evidência explícita.
7. Deve haver annotation guideline/codebook.
8. Preferencialmente usar dois ou mais especialistas.
9. Discordâncias devem passar por adjudicação.
10. Deve-se medir inter-rater agreement.
11. O Golden Dataset deve ser dividido em train/validation/test.
12. Somente o training set deve ser usado diretamente no fine-tuning.
13. GQS, mDISCERN e JAMA podem ser usados como dimensões auxiliares, mas não como ground truth de veracidade.
14. O principal gap identificado é a ausência de um gold-standard dataset claim-level de misinformation GLP-1 desenhado especificamente para fine-tuning e avaliação de LLMs.

---

# 20. Título sugerido para este chat

**PhD — Golden Dataset e Classificação de Misinformation sobre GLP-1 com LLMs**
