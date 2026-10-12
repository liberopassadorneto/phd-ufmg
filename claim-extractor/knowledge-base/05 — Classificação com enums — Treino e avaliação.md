# LLM Enum Classification — Type-Safe Outputs, Evals, Métricas e Golden Dataset

## 1. Objetivo

Construir classificadores com LLMs que retornem **categorias predefinidas (enums)** de forma confiável, validável e mensurável.

Exemplo:

```ts
type TicketType =
  | "BUG"
  | "FEATURE_REQUEST"
  | "SUPPORT_REQUEST"
  | "INCIDENT"
  | "UNKNOWN";
```

A arquitetura recomendada é:

```text
Natural Language Input
        ↓
       LLM
        ↓
Structured Output / JSON Schema
        ↓
Runtime Validation
        ↓
Typesafe Enum
        ↓
Business Logic
```

A LLM faz a **classificação semântica**.  
O schema/validator garante que a saída esteja no formato esperado.

---

## 2. Type-safe enum output com LLM

Um exemplo com TypeScript + Zod:

```ts
import { z } from "zod";

const TicketType = z.enum([
  "BUG",
  "FEATURE_REQUEST",
  "SUPPORT_REQUEST",
  "INCIDENT",
  "UNKNOWN",
]);

const LLMOutput = z.object({
  type: TicketType,
  confidence: z.number().min(0).max(1),
});
```

Também é possível usar JSON Schema:

```json
{
  "type": "object",
  "properties": {
    "type": {
      "type": "string",
      "enum": [
        "BUG",
        "FEATURE_REQUEST",
        "SUPPORT_REQUEST",
        "INCIDENT",
        "UNKNOWN"
      ]
    },
    "confidence": {
      "type": "number",
      "minimum": 0,
      "maximum": 1
    }
  },
  "required": ["type", "confidence"],
  "additionalProperties": false
}
```

### Importante

Zod não classifica.

```text
LLM → classifica
Zod / JSON Schema → valida
```

Alternativas ao Zod:

- Valibot
- Yup
- Joi
- TypeBox
- io-ts
- ArkType
- JSON Schema
- Pydantic (Python)
- Jackson + enum (Java)
- typed constants + validação explícita (Go)

---

## 3. Como a LLM escolhe corretamente entre os enums

O schema apenas garante que a resposta esteja dentro dos valores permitidos.

A **qualidade semântica da classificação** depende de:

- definição clara de cada classe;
- exemplos few-shot;
- regras para fronteiras entre classes;
- categoria `UNKNOWN`;
- evidência/rationale quando necessário;
- avaliação com dataset rotulado;
- análise sistemática dos erros.

Exemplo de taxonomia:

```text
BUG
→ funcionalidade existente apresenta comportamento incorreto.

FEATURE_REQUEST
→ funcionalidade desejada ainda não existe.

SUPPORT_REQUEST
→ sistema funciona como esperado, mas o usuário precisa de ajuda.

INCIDENT
→ degradação/outage ativo em produção com impacto operacional.

UNKNOWN
→ informação insuficiente ou fora da taxonomia.
```

Se humanos não conseguem distinguir claramente duas classes, a LLM também tende a confundi-las.

---

## 4. Use cases

Classificação com enums pode ser usada em:

- roteamento para microserviços;
- seleção de agentes ou tools;
- intent detection;
- triagem de incidentes;
- extração estruturada;
- workflows de aprovação;
- moderação;
- classificação fiscal;
- query routing em RAG;
- state machines;
- classificação de claims;
- classificação de veracidade;
- classificação por tópico.

Princípio importante:

> A LLM deve atuar como interpretador semântico, e não como autoridade irrestrita sobre regras de negócio.

---

# 5. EVALs

## O que é um Eval

Um **Eval** é um processo sistemático para medir o comportamento da LLM contra respostas conhecidas.

Exemplo:

```json
{
  "input": "Checkout is down for all users.",
  "expected": "INCIDENT"
}
```

A LLM retorna:

```json
{
  "predicted": "INCIDENT"
}
```

Então:

```text
expected
vs
predicted
```

é usado para calcular métricas.

---

# 6. Métricas Offline

Métricas offline são calculadas quando existe **ground truth**.

## Accuracy

```text
Accuracy → qualidade global.
```

Percentual total de classificações corretas.

---

## Precision

```text
Precision → falsos positivos.
```

Pergunta:

> Quando o modelo diz que algo pertence a uma classe, com que frequência ele está correto?

Fórmula:

```text
Precision = TP / (TP + FP)
```

---

## Recall

```text
Recall → falsos negativos.
```

Pergunta:

> De todos os casos reais daquela classe, quantos o modelo conseguiu encontrar?

Fórmula:

```text
Recall = TP / (TP + FN)
```

Para classes críticas como `INCIDENT`, Recall pode ser mais importante que Precision.

---

## F1

```text
F1 → equilíbrio entre Precision e Recall.
```

Fórmula:

```text
F1 = 2 × (Precision × Recall) / (Precision + Recall)
```

Exemplo:

```text
Precision = 75%
Recall    = 90%

F1 ≈ 81.8%
```

---

## Macro F1

Calcula o F1 individual de cada classe e depois faz a média simples.

```text
Macro F1 → todas as classes têm o mesmo peso.
```

É especialmente útil em datasets desbalanceados.

---

## Weighted F1

Calcula F1 por classe e pondera pela quantidade de exemplos.

```text
Weighted F1 → classes mais frequentes têm mais peso.
```

---

## Micro F1

Agrega TP, FP e FN globalmente antes de calcular o F1.

Em classificação multiclass single-label, frequentemente fica igual ou muito próximo de Accuracy.

---

## Confusion Matrix

```text
Confusion Matrix → quais classes estão sendo confundidas.
```

Exemplo:

```text
                  Predicted
               BUG INCIDENT SUPPORT
Actual BUG       90     5      5
Actual INCIDENT  15    80      5
Actual SUPPORT    4     1     95
```

Permite identificar problemas específicos como:

```text
INCIDENT → BUG
```

---

## Calibration

```text
Calibration → se scores de confiança correspondem à taxa real de acerto.
```

Exemplo ideal:

```text
confidence 0.90–1.00 → ~95% de acerto
confidence 0.80–0.90 → ~85% de acerto
confidence 0.70–0.80 → ~75% de acerto
```

O confidence produzido pela LLM **não deve ser assumido automaticamente como probabilidade real**.

Ele precisa ser calibrado empiricamente.

---

## Brier Score

Mede o erro entre probabilidades previstas e o resultado verdadeiro.

```text
menor → melhor
```

---

## Expected Calibration Error (ECE)

Mede quanto a confiança declarada se distancia da accuracy observada.

---

## Per-class metrics

É importante calcular:

```text
Precision por classe
Recall por classe
F1 por classe
```

Porque uma boa Accuracy global pode esconder uma classe crítica com desempenho ruim.

---

## Robustness

Avalia se pequenas mudanças no texto preservam a classificação correta.

Exemplo:

```text
"Checkout is down"
"Checkout seems unavailable"
"Users cannot complete checkout"
```

---

## Regression Rate

Mede se uma nova versão quebra casos que antes estavam corretos.

```text
Prompt v1 → correto
Prompt v2 → incorreto
```

Isso é uma regressão.

---

## Slice Performance

Avalia subconjuntos específicos:

```text
PT-BR
English
Spanish
inputs curtos
inputs longos
edge cases
classes raras
casos ambíguos
```

---

# 7. Métricas Online

Online não existe necessariamente ground truth imediato.

Por isso as métricas são diferentes.

## Confidence Score

```text
Confidence → quão segura parece a resposta atual.
```

É um sinal operacional, não uma probabilidade confiável por padrão.

---

## Consensus Score

```text
Consensus → quanto múltiplas execuções/modelos concordam.
```

Exemplo:

```text
5 execuções

INCIDENT
INCIDENT
INCIDENT
INCIDENT
BUG
```

Consensus:

```text
4 / 5 = 0.80
```

---

## UNKNOWN Rate

```text
UNKNOWN Rate → percentual de casos classificados como UNKNOWN.
```

Um aumento pode indicar:

- drift;
- taxonomia incompleta;
- inputs novos;
- modelo pior;
- prompt inadequado.

---

## Human Review Rate

```text
Human Review Rate → percentual enviado para revisão humana.
```

---

## Human Override Rate

```text
Override Rate → quantas previsões humanas corrigem.
```

É um sinal muito útil de qualidade em produção.

---

## Acceptance Rate

Percentual das classificações aceitas sem alteração.

---

## Escalation Rate

Percentual encaminhado para:

- segunda LLM;
- modelo mais forte;
- regras adicionais;
- revisão humana.

---

## Class Distribution

Distribuição das classes em produção.

Mudanças bruscas podem indicar:

```text
mudança real dos dados
ou
problema de classificação
```

---

## Confidence Distribution

Monitora como os confidence scores estão se comportando ao longo do tempo.

---

## Consensus Distribution

Monitora estabilidade das classificações.

---

## Input Drift

Mudanças na distribuição ou natureza dos inputs.

---

## Prediction Drift

Mudanças na distribuição das classes produzidas pela LLM.

---

## Error Rate

Falhas técnicas como:

```text
invalid JSON
schema validation error
timeout
provider error
parsing error
```

---

## Fallback Rate

Percentual de requisições que precisaram usar fluxo alternativo.

---

## Latency

Tempo de resposta.

---

## Cost per Request

Custo médio por classificação.

---

## Token Usage

Quantidade de tokens consumidos.

---

## Availability

Percentual das classificações concluídas com sucesso.

---

# 8. Offline vs Online vs Eval

Uma forma simples de pensar:

```text
OFFLINE EVAL
→ "O sistema funciona bem em dados que já conhecemos?"
```

Métricas:

```text
Accuracy
Precision
Recall
F1
Confusion Matrix
Calibration
Robustness
Regression
```

---

```text
ONLINE MONITORING
→ "O sistema continua se comportando bem em produção?"
```

Métricas:

```text
Confidence
Consensus
UNKNOWN Rate
Human Review Rate
Override Rate
Class Distribution
Drift
Latency
Cost
Errors
```

---

```text
EVAL
→ processo usado para transformar resultados em evidência mensurável.
```

---

# 9. Production Ground Truth

Quando humanos revisam dados de produção, passa a existir ground truth.

Então é possível calcular:

```text
Production Accuracy
Production Precision
Production Recall
Production F1
Production Confusion Matrix
```

O ciclo fica:

```text
Golden Dataset
      ↓
Offline Evals
      ↓
Quality Gate
      ↓
Deploy
      ↓
Production Monitoring
      ↓
Human Review
      ↓
Ground Truth de produção
      ↓
Novo Eval Dataset
      ↓
Offline Evals novamente
      ↺
```

---

# 10. Golden Dataset

## Definição

Golden Dataset é um conjunto de exemplos cuja resposta correta foi definida de forma confiável.

Exemplo:

```json
{
  "input": "Checkout is unavailable for all users.",
  "expected": "INCIDENT"
}
```

Esse `expected` funciona como **ground truth**.

---

## Para que serve

Principalmente para:

```text
avaliar
e não ensinar
```

Você roda a LLM no Golden Dataset e compara:

```text
expected
vs
predicted
```

Depois calcula:

```text
Accuracy
Precision
Recall
F1
Confusion Matrix
Calibration
```

---

## Golden Dataset não é necessariamente treinamento

Existem três usos diferentes para dados rotulados:

### 1. Evaluation

```text
Golden Dataset
→ mede qualidade
```

### 2. Few-shot

Alguns exemplos rotulados são colocados diretamente no prompt.

```text
Input: ...
Output: INCIDENT
```

### 3. Fine-tuning

Dados rotulados podem ser usados para ajustar o modelo.

Se um exemplo foi usado para fine-tuning ou prompt engineering, ele não deve permanecer no holdout final de avaliação.

---

# 11. Development Dataset

Development Set é usado para construir e melhorar o classificador.

Pode ser usado para:

```text
prompt engineering
few-shot selection
taxonomia
análise de erros
threshold tuning
model selection
```

Você pode olhar seus erros e alterar o sistema com base neles.

---

# 12. Golden vs Development

Regra principal:

```text
Development Dataset
→ usado para aprender como construir o sistema

Golden Dataset
→ usado para descobrir se o sistema realmente generaliza
```

Exemplo com 100 registros:

```text
100 registros humanos rotulados
        ↓
70 → Development
30 → Golden / Holdout
```

Com poucos dados, 70/30 pode ser razoável.

---

# 13. Como criar os datasets

Fluxo recomendado:

```text
1. Definir os ENUMs
        ↓
2. Criar annotation guidelines
        ↓
3. Coletar dados representativos
        ↓
4. Humanos rotulam
        ↓
5. Resolver discordâncias
        ↓
6. Remover duplicatas / near-duplicates
        ↓
7. Fazer split
        ↓
Development + Golden
```

---

# 14. Annotation Guidelines

Antes da rotulagem, documente claramente cada classe.

Exemplo:

```text
BUG
→ funcionalidade existente se comporta incorretamente.

INCIDENT
→ problema ativo de produção com impacto operacional.

FEATURE_REQUEST
→ funcionalidade solicitada não existe.

SUPPORT_REQUEST
→ usuário precisa de ajuda usando funcionalidade existente.

UNKNOWN
→ informação insuficiente.
```

---

# 15. Human Annotation

Idealmente mais de um anotador.

Exemplo:

```text
Annotator A → INCIDENT
Annotator B → INCIDENT

final → INCIDENT
```

Caso haja discordância:

```text
Annotator A → BUG
Annotator B → INCIDENT
```

faz-se:

```text
adjudicação
     ↓
Final Label → INCIDENT
```

---

# 16. Stratified Split

Não divida os dados sem preservar minimamente a distribuição das classes.

Exemplo:

```text
Dataset total

BUG        40
SUPPORT    25
FEATURE    15
INCIDENT   10
UNKNOWN    10
```

Split aproximado:

```text
Development    Golden

BUG      28    BUG      12
SUPPORT  18    SUPPORT   7
FEATURE  10    FEATURE   5
INCIDENT  7    INCIDENT  3
UNKNOWN   7    UNKNOWN   3
```

---

# 17. Evitar Data Leakage

Não coloque variações semânticas do mesmo caso em development e golden.

Ruim:

```text
Development:
"Checkout is down for all users."

Golden:
"Checkout is unavailable for every user."
```

São semanticamente quase o mesmo caso.

Melhor fazer split por:

```text
origem
ticket
documento
usuário
vídeo
thread
grupo semântico
```

---

# 18. Estrutura possível de arquivos

```text
datasets/

├── development.jsonl
├── golden.jsonl
└── annotation_guidelines.md
```

Exemplo `development.jsonl`:

```json
{"id":"001","text":"Checkout fails on Safari","label":"BUG"}
{"id":"002","text":"Can we add Apple Pay?","label":"FEATURE_REQUEST"}
```

Exemplo `golden.jsonl`:

```json
{"id":"081","text":"Production checkout is down","label":"INCIDENT"}
{"id":"082","text":"Button fails only in Firefox","label":"BUG"}
```

---

# 19. Metadata recomendada

Estrutura mais robusta:

```json
{
  "id": "081",
  "text": "Production checkout is down for all users.",
  "label": "INCIDENT",
  "language": "en",
  "source": "production_ticket",
  "difficulty": "easy",
  "annotator_1": "INCIDENT",
  "annotator_2": "INCIDENT",
  "agreement": true,
  "adjudicated": false
}
```

Para caso difícil:

```json
{
  "id": "094",
  "text": "Some users cannot checkout since the latest deploy.",
  "label": "INCIDENT",
  "difficulty": "hard",
  "annotator_1": "BUG",
  "annotator_2": "INCIDENT",
  "agreement": false,
  "adjudicated": true
}
```

---

# 20. Aplicação ao projeto de Claim Extraction / GLP-1

No projeto de desinformação sobre GLP-1, a mesma separação pode ser usada para:

```text
claim_type
topic
veracity
harmfulness
```

Exemplo de claim:

```json
{
  "claim_id": "video_042_claim_03",
  "claim": "Ozempic faz qualquer pessoa perder 20 kg em um mês.",
  "topic": "INDICATION",
  "veracity": "INACCURATE",
  "harmfulness": "HIGH"
}
```

Nesse contexto:

```text
Development Set
→ prompt engineering
→ few-shot
→ escolha de modelo
→ ajustes de taxonomia
→ análise de erros
```

Enquanto:

```text
Golden / Holdout Set
→ benchmark final
→ Accuracy
→ Precision
→ Recall
→ Macro F1
→ Confusion Matrix
→ Calibration
```

Para **claim extraction** propriamente dita, classificação por enum não é suficiente.

Também devem ser usadas métricas específicas de extração, como:

```text
Atomicity
Faithfulness
Coverage
Decontextualization
Fluency
Focus
Redundancy
F_fact
```

Assim, o projeto pode avaliar duas dimensões diferentes:

```text
CLAIM EXTRACTION
→ qualidade dos claims produzidos

CLAIM CLASSIFICATION
→ qualidade dos enums atribuídos aos claims
```

---

# 21. Arquitetura geral recomendada

```text
Human-annotated source data
            ↓
      Reliable labels
            ↓
   ┌────────┴────────┐
   ↓                 ↓
Development       Golden
Dataset            Dataset
   ↓                 ↓
Prompt            Offline Eval
Few-shot          Accuracy
Model choice      Precision
Taxonomy          Recall
Thresholds        F1
   ↓              Confusion Matrix
   └────────┬────────┘
            ↓
          Deploy
            ↓
   Production Monitoring
            ↓
Confidence / Consensus
UNKNOWN / Human Review
Drift / Cost / Latency
            ↓
      Human Feedback
            ↓
   New Ground Truth
            ↓
     Future Eval Set
            ↺
```

---

# 22. Resumo final

```text
LLM
→ classifica semanticamente

Schema / Zod / JSON Schema
→ valida estrutura

Development Dataset
→ serve para construir e melhorar o sistema

Golden Dataset
→ serve para medir se o sistema realmente funciona

Offline Metrics
→ medem qualidade contra ground truth

Online Metrics
→ monitoram comportamento em produção

EVALs
→ processo sistemático que transforma essas métricas em evidência
```

A regra principal é:

> **Development Dataset é onde você aprende como construir o classificador. Golden Dataset é onde você verifica se aquilo que construiu realmente generaliza para dados que não foram usados no desenvolvimento.**
