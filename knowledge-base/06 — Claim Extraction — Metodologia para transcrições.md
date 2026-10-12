# PhD — Pipeline e Metodologia para Claim Extraction em Transcripts de Vídeos

## 1. Objetivo

Definir uma metodologia científica para transformar transcripts de vídeos do YouTube em **claims atômicos, autocontidos e rastreáveis**, que depois possam ser classificados por uma estrutura hierárquica de labels.

Exemplo de saída final desejada:

```json
[
  {
    "claim_id": "C001",
    "claim": "Ozempic é um medicamento usado no tratamento do diabetes tipo 2.",
    "claim_type": "FACTUAL_MEDICAL_CLAIM",
    "topic": "INDICATION",
    "veracity": "ACCURATE"
  }
]
```

A principal decisão metodológica desta conversa foi **separar Claim Extraction de Claim Classification**.

---

## 2. Separação entre Claim Extraction e Classification

O Claim Extractor deve responder:

> Quais afirmações verificáveis estão sendo feitas neste trecho do transcript?

Ele **não deve**, nessa etapa, decidir se o claim é verdadeiro, falso, misleading, nem classificá-lo por tópico clínico.

Assim:

```text
Transcript
    ↓
Claim Extraction
    ↓
Claims estruturados
    ↓
Hierarchical Classification
    ↓
claim_type / topic / veracity / misinformation_type
```

Essa separação permite identificar com clareza a origem de erros:

```text
erro de segmentação
erro de claim span detection
erro de decomposição atômica
erro de decontextualização
hallucination / falta de faithfulness
erro de topic classification
erro de veracity classification
```

---

## 3. Literatura científica principal discutida

### 3.1 Ullrich et al. (2025) — Claim Extraction for Fact-Checking

Trabalho central para o projeto.

Contribuições relevantes:

- formaliza Claim Extraction como uma tarefa de `texto → múltiplos claims`;
- propõe o dataset **FEVERFact**;
- trabalha com claims simples, autocontidos e fiéis ao texto;
- utiliza aproximadamente **4,4 mil documentos** e **17 mil claims**;
- avalia Claim Extraction com métricas específicas;
- compara abordagens como:
  - QACG;
  - few-shot prompting com LLMs;
  - fine-tuning;
  - modelos seq2seq.

Métricas destacadas:

- Atomicity;
- Fluency;
- Decontextualization;
- Faithfulness;
- Focus;
- Coverage;
- Redundancy.

---

### 3.2 Deng et al. (ACL 2024) — Document-level Claim Extraction and Decontextualisation

Muito relevante para transcripts longos.

Pipeline geral:

```text
document
  ↓
sentence extraction
  ↓
context generation
  ↓
decontextualization
  ↓
check-worthiness estimation
```

Contribuição importante para o projeto:

- textos longos não precisam ser processados integralmente de uma vez;
- primeiro podem ser encontrados trechos/sentenças candidatas;
- depois esses trechos são transformados em claims standalone.

---

### 3.3 Sundriyal et al. (EMNLP 2022) — Automatic Identification of Claim Spans

Introduz a tarefa de **Claim Span Identification**.

Objetivo:

> localizar exatamente qual trecho do texto contém a informação verificável.

Exemplo:

```text
"Pessoal, eu uso Ozempic há meses e posso dizer que
ele não apresenta nenhum efeito colateral sério."
```

Claim span:

```text
"ele não apresenta nenhum efeito colateral sério"
```

Esse passo é útil porque transcripts também contêm:

- introduções;
- saudações;
- opinião;
- piadas;
- chamadas para ação;
- propaganda;
- histórias pessoais;
- repetições.

Nem todo texto deve virar claim.

---

### 3.4 Min et al. (EMNLP 2023) — FActScore

Contribuição principal: conceito operacional de **atomic facts**.

Um atomic fact deve conter uma única unidade de informação verificável.

Exemplo:

```text
"Ozempic foi desenvolvido para diabetes tipo 2,
reduz o apetite, faz perder peso e praticamente
não causa efeitos colaterais."
```

Deve ser decomposto em:

```text
C001 — Ozempic é usado no tratamento do diabetes tipo 2.
C002 — Ozempic reduz o apetite.
C003 — Ozempic pode causar perda de peso.
C004 — Ozempic praticamente não causa efeitos adversos.
```

Regra importante:

```text
1 atomic claim
≈
1 proposição verificável
≈
1 relação ou processo factual principal
```

Uma frase pode produzir:

```text
0 claims
1 claim
N claims
```

E várias frases podem ser necessárias para construir um único claim.

---

### 3.5 Choi et al. (TACL 2021) — Decontextualization

Objetivo:

> transformar uma sentença dependente de contexto em uma sentença que possa ser entendida sozinha, sem alterar seu significado.

Exemplo:

```text
"Ela também reduz o apetite."
```

pode virar:

```text
"Semaglutida reduz o apetite."
```

quando o contexto deixa claro que "ela" significa semaglutida.

Regra essencial:

- usar somente informações disponíveis no contexto;
- não adicionar conhecimento externo;
- quando uma referência não puder ser resolvida, marcar como context-dependent ou unresolved.

---

### 3.6 Pan et al. (ACL 2021) — QACG

Pipeline de geração de claims baseada em:

```text
Named Entity Recognition
    ↓
Question Generation
    ↓
Question Answering
    ↓
Declarative Claim
```

Pode servir como **baseline experimental** alternativo ao LLM Claim Extractor.

---

### 3.7 Hierarchical Claim Classification

A literatura de hierarchical claim classification é mais relevante para a etapa posterior:

```text
Claim
  ↓
claim_type
  ↓
topic
  ↓
veracity
  ↓
misinformation_type
```

Ou seja, não deve ser confundida com a etapa de Claim Extraction propriamente dita.

---

## 4. Pipeline proposta — Claim Extractor V1

Pipeline consolidada:

```text
YOUTUBE VIDEOS
      ↓
TRANSCRIPTS
      ↓
Transcript Preprocessing
      ↓
Context Window Builder
      ↓
Claim Span Detection
      ↓
Atomic Claim Decomposition
      ↓
Claim Normalization / Canonicalization
      ↓
Decontextualization
      ↓
Faithfulness Validation
      ↓
Deduplication / Consolidation
      ↓
CLAIM DATASET
      ↓
Hierarchical Claim Classification
```

Versão simplificada:

```text
Transcript
   ↓
Candidate Span
   ↓
Atomic Claims
   ↓
Standalone Claims
   ↓
Validated Claims
   ↓
claims.jsonl
```

---

## 5. Transcript Preprocessing

O transcript deve preservar a proveniência temporal.

Exemplo:

```json
{
  "video_id": "VID001",
  "segments": [
    {
      "segment_id": "S001",
      "start": 124.2,
      "end": 132.8,
      "text": "O Ozempic foi criado para diabetes tipo 2..."
    }
  ]
}
```

Isso permite rastrear qualquer claim até:

```text
claim
↓
vídeo
↓
timestamp
↓
trecho original
```

Essa rastreabilidade será importante para:

- avaliação humana;
- auditoria;
- reprodução dos experimentos;
- revisão de erros.

---

## 6. Context Windows

Claims frequentemente dependem de frases anteriores.

Exemplo:

```text
Semaglutida é utilizada nesses medicamentos.
Ela também reduz o apetite.
Isso acontece porque ela age diretamente queimando gordura.
```

A frase isolada:

```text
"Isso acontece porque ela age diretamente queimando gordura."
```

não resolve:

- "isso";
- "ela".

Por isso é recomendado trabalhar com pequenas janelas contextuais, por exemplo:

```text
S[n-2]
S[n-1]
S[n]
S[n+1]
S[n+2]
```

A janela pode ser usada somente para interpretação; o `source_span` original deve continuar preservado.

---

## 7. Claim Span Detection

Objetivo:

> decidir se existe uma afirmação verificável naquele trecho e, se existir, localizar exatamente seu span.

Exemplo de saída intermediária:

```json
{
  "span_id": "S001-CAND-01",
  "source_text": "ele não apresenta nenhum efeito colateral sério"
}
```

Esse estágio pode atuar como filtro antes de enviar conteúdo para o decompositor.

---

## 8. Atomic Claim Decomposition

Objetivo:

> quebrar spans complexos em claims minimais e verificáveis.

Exemplo:

```text
Ozempic reduz o apetite, ajuda a emagrecer e não causa efeitos colaterais.
```

Decomposição:

```text
C001 — Ozempic reduz o apetite.
C002 — Ozempic ajuda na perda de peso.
C003 — Ozempic não causa efeitos colaterais.
```

A atomicidade facilita:

- fact-checking;
- classificação por tópico;
- classificação de veracidade;
- identificação de misinformation;
- avaliação humana;
- criação do golden dataset.

---

## 9. Decontextualization

Depois da decomposição, cada claim deve ser compreensível sozinho.

Exemplo:

```text
"Esse remédio não tem riscos."
```

Contexto:

```text
"Estamos falando do Ozempic..."
```

Saída:

```text
"Ozempic não apresenta riscos à saúde."
```

Mas somente quando o contexto permitir a resolução inequívoca da referência.

---

## 10. Faithfulness

Faithfulness responde:

> O vídeo realmente afirmou o conteúdo presente no claim?

Não deve ser confundido com veracity.

Exemplo:

```text
Transcript:
"Ozempic não possui efeitos adversos."

Claim:
"Ozempic não possui efeitos adversos."
```

Resultado:

```text
Faithfulness = YES
Veracity = ainda não avaliada
```

Mesmo que o claim seja cientificamente falso, ele continua sendo **faithful** ao transcript.

### Distinção central

```text
Faithfulness:
"O transcript realmente disse isso?"

Veracity:
"O que foi dito é verdadeiro?"
```

Essa separação deve permanecer em toda a arquitetura do projeto.

---

## 11. Deduplicação e consolidação

Vídeos podem repetir semanticamente a mesma afirmação.

Exemplo:

```text
"Ozempic não dá problema nenhum."

"Esse remédio é totalmente seguro."

"Como eu disse, não tem risco nenhum."
```

Em vez de gerar três claims independentes, é possível manter:

```json
{
  "claim_id": "C001",
  "claim": "Ozempic não apresenta riscos à saúde.",
  "occurrences": [
    {
      "start": 120.4,
      "end": 124.8
    },
    {
      "start": 514.2,
      "end": 520.1
    }
  ]
}
```

Assim:

- o claim canônico não é duplicado;
- as ocorrências continuam rastreáveis;
- a frequência/repetição do claim no vídeo não é perdida.

---

## 12. Métricas para o Claim Extractor

### Atomicity

Pergunta:

> O claim contém apenas uma proposição factual principal?

---

### Fluency

Pergunta:

> O claim é gramaticalmente e semanticamente compreensível?

---

### Decontextualization

Pergunta:

> O claim pode ser compreendido sem consultar o transcript original?

---

### Faithfulness

Pergunta:

> O claim é inteiramente sustentado pelo texto de origem?

---

### Focus

Pergunta:

> O sistema está gerando apenas claims relevantes ou também produz muito ruído?

---

### Coverage

Pergunta:

> Todos os claims relevantes existentes no texto foram extraídos?

---

### Redundancy

Pergunta:

> Quantos claims gerados repetem essencialmente a mesma informação?

---

## 13. Trade-off Focus × Coverage

Existe um trade-off importante:

```text
Extractor conservador
→ pouco ruído
→ alto Focus
→ pode perder claims
→ Coverage menor
```

versus:

```text
Extractor agressivo
→ encontra mais claims
→ Coverage maior
→ pode gerar conteúdo irrelevante
→ Focus menor
```

Essa relação provavelmente deverá fazer parte da avaliação experimental.

---

## 14. Estrutura sugerida para o Claim Extraction Dataset

Antes da classificação hierárquica, utilizar uma estrutura próxima a:

```json
{
  "claim_id": "C003",
  "video_id": "VID001",

  "source": {
    "start_time": 412.3,
    "end_time": 419.8,
    "text": "Esse remédio não tem efeitos colaterais importantes."
  },

  "context": {
    "previous": "Estamos falando aqui do Ozempic.",
    "next": "Por isso eu considero ele muito seguro."
  },

  "claim": "Ozempic não apresenta efeitos adversos importantes.",

  "quality": {
    "atomic": true,
    "decontextualized": true,
    "faithful_to_source": true
  }
}
```

Importante: nessa etapa ainda não aparecem:

```text
claim_type
topic
veracity
misinformation_type
```

Esses labels pertencem à próxima pipeline.

---

## 15. Hierarchical Claim Classifier

Depois que o Claim Extractor produzir claims confiáveis:

```text
Claim
  ↓
Claim Type
  ↓
Topic
  ↓
Veracity
  ↓
Misinformation Type
```

Exemplo final:

```json
{
  "claim_id": "C003",
  "claim": "Ozempic não apresenta efeitos adversos importantes.",
  "claim_type": "FACTUAL_MEDICAL_CLAIM",
  "topic": "ADVERSE_EFFECT",
  "veracity": "MISLEADING",
  "misinformation_type": "RISK_MINIMIZATION"
}
```

---

## 16. Proposta experimental inicial

Podemos construir um experimento com:

```text
Gold Human Claims
        │
        ├── Baseline A: QACG
        ├── Baseline B: LLM Few-Shot
        ├── Baseline C: Fine-Tuned LLM
        └── Proposed Claim Extractor
```

Todos os sistemas seriam avaliados sobre os mesmos transcripts.

Métricas:

```text
Atomicity
Faithfulness
Decontextualization
Fluency
Focus
Coverage
Redundancy
```

Essa arquitetura permite comparar diferentes abordagens de Claim Extraction de maneira controlada.

---

## 17. Hipótese de metodologia geral

A pesquisa pode ser organizada em duas grandes pipelines independentes:

### Pipeline A — Claim Extraction

```text
Transcript
↓
Preprocessing
↓
Claim Span Identification
↓
Atomic Claim Decomposition
↓
Normalization
↓
Decontextualization
↓
Faithfulness Check
↓
Deduplication
↓
Claim Dataset
```

### Pipeline B — Claim Classification

```text
Claim Dataset
↓
Claim Type
↓
Topic
↓
Veracity
↓
Misinformation Type
↓
Final Structured Dataset
```

Essa separação permite avaliar cada componente isoladamente e realizar estudos de ablação.

---

## 18. Próximo passo recomendado

Antes de selecionar modelos, fazer fine-tuning ou criar os labels de veracidade, o próximo passo metodológico deve ser definir as **Annotation Guidelines do Golden Dataset do Claim Extractor**.

Precisamos formalizar:

- o que é um claim;
- o que não é um claim;
- quando uma frase produz zero claims;
- quando deve ser quebrada em dois ou mais claims;
- como tratar experiências pessoais;
- como tratar opiniões;
- como tratar recomendações;
- como tratar perguntas;
- como tratar hipóteses;
- como tratar afirmações vagas;
- como tratar propaganda;
- como lidar com coreferência;
- como resolver expressões como "ele", "isso", "esse remédio";
- quando decontextualizar;
- quando marcar como unresolved;
- como avaliar atomicidade;
- como avaliar faithfulness;
- como lidar com claims repetidos.

Essas regras devem ser congeladas antes da anotação humana do golden dataset para garantir consistência e reprodutibilidade.

---

## 19. Referências-base

- Thorne et al. (2018). **FEVER: a Large-scale Dataset for Fact Extraction and VERification.**
- Choi et al. (2021). **Decontextualization: Making Sentences Stand-Alone.** TACL.
- Pan et al. (2021). Trabalho baseado em **Question-Answer Generation for Claim Generation (QACG)**.
- Sundriyal et al. (2022). **Empowering the Fact-checkers! Automatic Identification of Claim Spans on Twitter.** EMNLP.
- Min et al. (2023). **FActScore: Fine-grained Atomic Evaluation of Factual Precision in Long Form Text Generation.** EMNLP.
- Deng et al. (2024). **Document-level Claim Extraction and Decontextualisation for Fact-Checking.** ACL.
- Ullrich et al. (2025). **Claim Extraction for Fact-Checking: Data, Models, and Automated Metrics.** FEVERFact.

---

## 20. Resumo da decisão atual

A arquitetura de referência adotada nesta etapa é:

```text
100 YouTube Videos
        ↓
100 Transcripts
        ↓
Claim Span Identification
        ↓
Atomic Claim Decomposition
        ↓
Normalization
        ↓
Decontextualization
        ↓
Faithfulness Validation
        ↓
Deduplication
        ↓
Golden / Generated Claim Dataset
        ↓
[segunda etapa]
Hierarchical Classification
        ↓
claim_type
topic
veracity
misinformation_type
```

O foco imediato do projeto deve permanecer no **Claim Extractor**, sem misturar ainda a avaliação da veracidade dos claims.
