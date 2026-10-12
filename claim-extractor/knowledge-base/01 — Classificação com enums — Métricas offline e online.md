# LLM Enum Classification: Type-Safe Outputs, Evals e Métricas de Confiabilidade

## 1. Visão geral

Ao usar uma LLM para classificação, a ideia é transformar texto livre em uma saída estruturada e restrita a um conjunto conhecido de valores.

Exemplo:

```text
Input:
"Meu cartão foi cobrado duas vezes."

Output esperado:
DUPLICATE_PAYMENT
```

Em vez de deixar a LLM responder em texto livre, usamos um contrato estruturado:

```json
{
  "category": "DUPLICATE_PAYMENT"
}
```

A arquitetura conceitual fica assim:

```text
Texto livre
   ↓
LLM
   ↓
Structured Output / JSON Schema
   ↓
Validação em runtime
   ↓
Enum / tipo seguro
   ↓
Business Logic
```

A LLM faz a **classificação semântica**.  
O schema, Zod, Pydantic, Jackson ou outra biblioteca apenas garante que a saída está dentro do contrato permitido.

---

## 2. Type-safe enum classification

Exemplo de enum:

```ts
enum TicketType {
  BUG = "BUG",
  FEATURE_REQUEST = "FEATURE_REQUEST",
  SUPPORT_REQUEST = "SUPPORT_REQUEST",
  INCIDENT = "INCIDENT",
  UNKNOWN = "UNKNOWN"
}
```

A LLM não classifica corretamente apenas porque os enums existem.

É necessário fornecer:

- nomes claros;
- descrição de cada categoria;
- regras de fronteira;
- exemplos;
- fallback como `UNKNOWN`;
- structured output.

Exemplo de definição semântica:

```text
BUG:
Defeito em uma funcionalidade existente sem evidência de impacto amplo em produção.

INCIDENT:
Degradação ou indisponibilidade ativa em produção, com impacto relevante em usuários e necessidade de resposta operacional.

FEATURE_REQUEST:
Pedido por uma funcionalidade que ainda não existe.

SUPPORT_REQUEST:
O sistema está funcionando, mas o usuário precisa de ajuda para utilizá-lo.

UNKNOWN:
Não há informação suficiente para classificar de forma confiável.
```

---

## 3. Structured Output não garante classificação correta

Há dois problemas diferentes:

```text
1. Output validity
2. Semantic correctness
```

Structured output resolve principalmente o primeiro.

Exemplo:

```json
{
  "category": "INCIDENT"
}
```

Pode ser estruturalmente válido e semanticamente errado.

Por isso, além de schema validation, precisamos de **EVALs**.

---

## 4. Bibliotecas e alternativas ao Zod

Zod não é a única opção.

### TypeScript / JavaScript

- Zod
- Valibot
- Joi
- Yup
- TypeBox
- io-ts
- ArkType
- JSON Schema diretamente

### Python

- Pydantic
- dataclasses + validação
- JSON Schema

### Java

- `enum`
- Jackson
- Bean Validation

### Go

- custom string types;
- constants;
- validators;
- JSON Schema.

O princípio é sempre o mesmo:

```text
LLM
   ↓
Structured Output
   ↓
Runtime Validation
   ↓
Domain Type
```

---

# 5. O que é um EVAL

Um **eval** é um teste sistemático para medir se o comportamento da LLM está correto.

Exemplo:

```text
Input:
"Checkout is down for all users."

Expected:
INCIDENT

Predicted:
INCIDENT
```

Se `expected == predicted`, o caso passou.

Dataset de exemplo:

```ts
const evalDataset = [
  {
    input: "Checkout is down for all users.",
    expected: "INCIDENT"
  },
  {
    input: "Can we export reports as CSV?",
    expected: "FEATURE_REQUEST"
  },
  {
    input: "How do I reset my password?",
    expected: "SUPPORT_REQUEST"
  }
];
```

Um eval run produz métricas como:

```text
Accuracy
Precision
Recall
F1
Confusion Matrix
Calibration
```

---

# 6. Métricas offline

Offline significa avaliar o sistema em um dataset no qual existe **ground truth**.

## Accuracy

**Accuracy → qualidade global.**

```text
Accuracy = previsões corretas / total de exemplos
```

Exemplo:

```text
940 classificações corretas
1000 exemplos

Accuracy = 94%
```

É útil, mas pode esconder problemas em classes raras.

---

## Precision

**Precision → falsos positivos.**

Pergunta:

> Quando o modelo diz que algo pertence a uma classe, quantas vezes ele está correto?

```text
Precision = TP / (TP + FP)
```

Exemplo para `INCIDENT`:

```text
Modelo marcou 120 casos como INCIDENT
90 realmente eram INCIDENT

Precision = 90 / 120 = 75%
```

Precision baixa significa muitos falsos alarmes.

---

## Recall

**Recall → falsos negativos.**

Pergunta:

> De todos os casos que realmente pertenciam à classe, quantos foram encontrados?

```text
Recall = TP / (TP + FN)
```

Exemplo:

```text
100 incidentes reais
90 identificados corretamente

Recall = 90%
```

Recall baixo significa que muitos casos reais estão escapando.

Para classes críticas, como `INCIDENT`, recall costuma ser especialmente importante.

---

## F1

**F1 → equilíbrio entre Precision e Recall.**

```text
F1 = 2 * (Precision * Recall) / (Precision + Recall)
```

Exemplo:

```text
Precision = 75%
Recall    = 90%

F1 ≈ 81.8%
```

F1 pune situações em que uma das duas métricas é muito baixa.

---

## Macro F1

**Macro F1 → média do F1 entre todas as classes, dando o mesmo peso a cada uma.**

É útil quando classes raras também são importantes.

---

## Weighted F1

**Weighted F1 → média do F1 ponderada pela frequência de cada classe.**

Classes mais frequentes têm maior influência.

---

## Micro F1

**Micro F1 → calcula TP, FP e FN globalmente antes de calcular F1.**

Em classificação multi-classe single-label, tende a ser igual ou muito próximo de Accuracy.

---

## Confusion Matrix

**Confusion Matrix → quais classes estão sendo confundidas.**

Exemplo:

```text
Actual ↓ / Predicted →

             BUG  FEATURE SUPPORT INCIDENT
BUG           90      2      6       2
FEATURE        4     92      3       1
SUPPORT        8      3     87       2
INCIDENT      15      0      5      80
```

Insight:

```text
INCIDENT → BUG
```

é um erro frequente.

Isso ajuda a melhorar:

- prompt;
- taxonomia;
- exemplos;
- definições de fronteira.

---

## False Positive Rate

**False Positive Rate → com que frequência o sistema acusa uma classe quando ela não era verdadeira.**

---

## False Negative Rate

**False Negative Rate → com que frequência o sistema deixa passar uma classe verdadeira.**

---

## Calibration

**Calibration → se os scores de confiança realmente correspondem à probabilidade observada de acerto.**

Exemplo:

```text
Confidence prevista    Accuracy real

0.90–1.00              97%
0.80–0.90              89%
0.70–0.80              80%
```

Se `confidence = 0.95` corresponde a apenas 70% de acerto, o score está mal calibrado.

---

## Brier Score

**Brier Score → mede a diferença entre probabilidade prevista e resultado real.**

Quanto menor, melhor.

---

## Expected Calibration Error — ECE

**ECE → mede quanto a confiança prevista se distancia da accuracy observada.**

---

## Regression Rate

**Regression Rate → quantos casos que funcionavam antes passaram a falhar após uma mudança.**

Útil ao comparar:

```text
Prompt v10
vs
Prompt v11
```

ou:

```text
Model A
vs
Model B
```

---

## Robustness

**Robustness → se pequenas mudanças no input preservam a classificação correta.**

Exemplo:

```text
"Fui cobrado duas vezes."
"Me cobraram 2x."
"Apareceram duas cobranças no cartão."
```

Todos deveriam resultar em:

```text
DUPLICATE_PAYMENT
```

---

## Slice Performance

**Slice Performance → qualidade em subconjuntos específicos.**

Exemplos:

```text
PT-BR
English
Spanish
mensagens curtas
mensagens longas
typos
casos ambíguos
classes críticas
```

---

# 7. Métricas online

Online significa monitorar o comportamento do sistema em produção.

Nem sempre existe ground truth imediatamente.

## Confidence Score

**Confidence → quão segura parece a resposta atual para o modelo.**

Exemplo:

```json
{
  "category": "INCIDENT",
  "confidence": 0.93
}
```

Esse valor não deve ser tratado automaticamente como uma probabilidade real.

Ele precisa ser calibrado usando evals offline.

---

## Consensus Score

**Consensus → quão estável é a classificação entre múltiplas execuções ou modelos.**

Exemplo:

```text
Run 1 → INCIDENT
Run 2 → INCIDENT
Run 3 → INCIDENT
Run 4 → BUG
Run 5 → INCIDENT

Consensus = 4 / 5 = 80%
```

Consensus baixo pode indicar:

- ambiguidade;
- taxonomia fraca;
- input insuficiente;
- instabilidade do modelo.

---

## UNKNOWN Rate

**UNKNOWN Rate → quantas entradas o sistema não consegue classificar com segurança.**

Aumento inesperado pode indicar:

- drift;
- nova categoria ainda não prevista;
- mudança nos inputs;
- problema no prompt.

---

## Abstention Rate

**Abstention Rate → percentual de casos em que o sistema decide não automatizar.**

Pode levar para:

```text
UNKNOWN
manual review
secondary validator
```

---

## Human Review Rate

**Human Review Rate → quanto do tráfego precisa de revisão humana.**

---

## Human Override Rate

**Human Override Rate → com que frequência o humano muda a classificação da LLM.**

Um override rate crescente pode indicar regressão.

---

## Acceptance Rate

**Acceptance Rate → quantas classificações são aceitas sem alteração.**

---

## Escalation Rate

**Escalation Rate → quantos casos precisam de uma segunda camada de validação.**

---

## Class Distribution

**Class Distribution → como os enums estão distribuídos em produção.**

Exemplo:

```text
Normal:

BUG       35%
SUPPORT   40%
FEATURE   20%
INCIDENT   5%
```

Se `INCIDENT` passa para 40%, isso merece investigação.

---

## Confidence Distribution

**Confidence Distribution → como os scores de confiança estão distribuídos ao longo do tempo.**

---

## Consensus Distribution

**Consensus Distribution → como a estabilidade das classificações varia ao longo do tempo.**

---

## Input Drift

**Input Drift → mudança nas características das entradas recebidas.**

Exemplos:

- novo idioma;
- textos mais longos;
- novos produtos;
- novo vocabulário;
- novos tipos de pedido.

---

## Prediction Drift

**Prediction Drift → mudança na distribuição das classes previstas.**

---

## Latency

**Latency → tempo para obter a classificação.**

---

## Cost per Request

**Cost per Request → custo médio de cada classificação.**

---

## Token Usage

**Token Usage → quantidade de tokens consumida.**

---

## Error Rate

**Error Rate → falhas técnicas de execução.**

Exemplos:

- timeout;
- invalid JSON;
- schema violation;
- API failure.

---

## Availability

**Availability → percentual das requisições completadas com sucesso.**

---

# 8. Como aplicar EVALs às métricas

Nem toda métrica é um eval.

O eval é o **processo de avaliação**.

As métricas são os resultados usados para interpretar esse processo.

## Offline Eval

Fluxo:

```text
Golden / Eval Dataset
        ↓
Prompt + Model
        ↓
Prediction
        ↓
Expected vs Predicted
        ↓
Metrics
```

Principais métricas:

```text
Accuracy
Precision
Recall
F1
Macro F1
Weighted F1
Confusion Matrix
Calibration
Robustness
Regression
Slice Performance
```

---

# 9. Calibration Eval

Confidence e consensus também devem ser validados offline.

Exemplo:

```text
Confidence >= 0.90
→ 98% de acerto observado
```

Então essa evidência pode justificar uma regra de produção:

```ts
if (confidence >= 0.90) {
  autoProcess();
}
```

Mas o threshold deve ser derivado do eval, e não escolhido arbitrariamente.

---

# 10. Consensus Eval

É possível medir empiricamente:

```text
Consensus       Accuracy real

100%            98.8%
80%             95.4%
60%             82.1%
<60%            61.7%
```

Assim, consensus deixa de ser apenas um número intuitivo e passa a ser um sinal validado.

---

# 11. Online Eval e Production Monitoring

Em produção normalmente não temos ground truth imediatamente.

Por isso monitoramos:

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
Failures
```

Quando depois surge uma resposta humana ou canonical label:

```text
Prediction
   ↓
Human review
   ↓
Ground truth
```

podemos calcular novamente:

```text
Production Accuracy
Production Precision
Production Recall
Production F1
Production Confusion Matrix
```

---

# 12. Ciclo ideal

```text
Golden Dataset
      ↓
Offline Evals
      ↓
Accuracy / Precision / Recall / F1
Confusion Matrix / Calibration
      ↓
Quality Gates
      ↓
Deploy
      ↓
Online Monitoring
      ↓
Confidence / Consensus / Drift
UNKNOWN / Human Review / Overrides
      ↓
Human Feedback
      ↓
Ground Truth de produção
      ↓
Novo Eval Dataset
      ↓
Offline Evals novamente
      ↺
```

---

# 13. Quality Gates

Antes de deploy, você pode definir requisitos mínimos.

Exemplo:

```text
Overall Accuracy >= 93%
Macro F1 >= 90%
INCIDENT Recall >= 97%
INCIDENT Precision >= 90%
High-confidence Accuracy >= 98%
```

Em código:

```ts
expect(metrics.accuracy)
  .toBeGreaterThanOrEqual(0.93);

expect(metrics.classes.INCIDENT.recall)
  .toBeGreaterThanOrEqual(0.97);

expect(metrics.classes.INCIDENT.precision)
  .toBeGreaterThanOrEqual(0.90);
```

---

# 14. Política de produção baseada em confidence e consensus

Exemplo:

```ts
if (
  confidence >= 0.90 &&
  consensus >= 0.80
) {
  autoProcess();
}
else if (
  confidence >= 0.75 &&
  consensus >= 0.60
) {
  runSecondaryValidator();
}
else {
  humanReview();
}
```

Para classes críticas:

```ts
if (category === "INCIDENT") {
  if (
    confidence < 0.95 ||
    consensus < 0.80
  ) {
    humanReview();
  }
}
```

Os thresholds devem ser justificados pelos evals.

---

# 15. Cost-sensitive evaluation

Nem todos os erros têm o mesmo custo.

Exemplo:

```text
Actual ↓ / Predicted →

             BUG  SUPPORT INCIDENT

BUG           0      1       2
SUPPORT       1      0       2
INCIDENT     10     10       0
```

Aqui:

```text
INCIDENT → BUG
```

custa muito mais que:

```text
SUPPORT → BUG
```

Por isso, além de métricas médias, pode ser necessário usar uma **cost matrix**.

---

# 16. Resumo mental

## Offline

**Accuracy** → qualidade global.

**Precision** → falsos positivos.

**Recall** → falsos negativos.

**F1** → equilíbrio entre Precision e Recall.

**Macro F1** → equilíbrio entre classes dando o mesmo peso para todas.

**Weighted F1** → F1 ponderado pela frequência das classes.

**Confusion Matrix** → quais classes estão sendo confundidas.

**Calibration** → se confidence corresponde à probabilidade real de acerto.

**Regression** → se uma nova versão quebrou algo que antes funcionava.

**Robustness** → se pequenas mudanças no input preservam a classificação.

**Slice Performance** → se o sistema funciona igualmente bem em diferentes grupos de dados.

---

## Online

**Confidence** → quão segura parece a classificação atual.

**Consensus** → quão estável é a classificação entre execuções ou modelos.

**UNKNOWN Rate** → quanto o sistema não consegue classificar.

**Human Review Rate** → quanto ainda depende de revisão humana.

**Override Rate** → com que frequência humanos corrigem a LLM.

**Class Distribution** → como as categorias aparecem em produção.

**Drift** → se os dados atuais mudaram em relação ao cenário validado.

**Latency** → velocidade.

**Cost** → custo operacional.

**Failure Rate** → confiabilidade técnica.

---

## EVAL

**Eval** → mecanismo usado para provar, com dados, se o comportamento do sistema é aceitável.

Perguntas que um bom eval deve responder:

```text
A Accuracy está acima do mínimo?

O Recall de classes críticas está alto o suficiente?

O modelo está confundindo quais categorias?

O confidence score está calibrado?

Consensus alto realmente significa maior confiabilidade?

O novo prompt melhorou ou piorou?

O modelo mais barato mantém qualidade suficiente?

O sistema funciona bem em PT-BR, espanhol e inglês?

Casos encontrados em produção já foram adicionados ao eval dataset?
```

---

# 17. Princípio final

A divisão principal é:

```text
Structured Output
→ "O modelo retornou um valor válido?"

Offline Evals
→ "O modelo escolheu o valor correto?"

Online Monitoring
→ "O sistema continua se comportando bem em produção?"

Human Feedback
→ "Como transformar erros reais em novos casos de avaliação?"
```

O ciclo completo deve conectar essas quatro partes continuamente.
