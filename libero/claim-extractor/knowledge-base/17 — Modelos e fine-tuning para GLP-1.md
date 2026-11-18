# Resumo — Modelos e fine-tuning para Claim Extraction em transcrições GLP-1

## 1. Objetivo

Construir e avaliar um sistema que transforme transcrições de vídeos do YouTube em português, sobre medicamentos agonistas de GLP-1, em claims:

- factuais;
- atômicas;
- fiéis ao conteúdo original;
- autossuficientes e decontextualizadas;
- vinculadas aos segmentos e trechos-fonte;
- estruturadas em JSON com campos tipados e valores enumerados.

A veracidade e a nocividade das claims não devem ser determinadas durante a extração. Essas propriedades pertencem a uma etapa posterior de verificação.

## 2. Desenho geral A/B/C

| Modelo | Papel | Estado inicial |
|---|---|---|
| A — científico | Baseline com evidência em artigo científico | Já treinado para Claim Extraction, por exemplo o checkpoint do FEVERFact baseado em Mistral |
| B — comunidade | Baseline open-weight especializado | Já treinado para Claim Extraction, sem adaptação inicial ao domínio GLP-1 |
| C — customizado | Modelo próprio para transcrições GLP-1 em PT-BR | Modelo Instruct geral que será especializado pelo projeto |

Configuração recomendada:

```text
MODEL A — científico
FEVERFact / qlora-mistral-instruct

MODEL B — comunidade
principled-intelligence/claim-extractor-2B-q-2605
ou claim-extractor-4B-q-2605

MODEL C — customizado
Qwen Instruct
+ dataset anotado de transcrições GLP-1
+ SFT
+ LoRA ou QLoRA
+ saída tipada por JSON Schema
```

## 3. Modelos já treinados para Claim Extraction

| Modelo | Especializado em Claim Extraction? | Observações |
|---|---:|---|
| `principled-intelligence/claim-extractor-2B-q-2605` | Sim | Melhor candidato para o primeiro teste local em 8 GB de VRAM |
| `principled-intelligence/claim-extractor-4B-q-2605` | Sim | Mais pesado; voltado originalmente a conversações e intents |
| `Luimas/claim-extractor-detective-qwen3b` | Sim | English-only; útil como referência de engenharia estruturada |
| FEVERFact `qlora-mistral-instruct` | Sim | Baseline científico treinado no contexto do FEVERFact |
| `Qwen/Qwen3.5-4B` | Não | Modelo geral; possível base para o Modelo C |
| `Qwen/Qwen3-4B-Instruct-2507` | Não | Modelo geral; candidato prático para QLoRA |
| `Ministral-3-3B-Instruct-2512` | Não | Modelo geral com boa capacidade de saída estruturada |
| `HuggingFaceTB/SmolLM3-3B` | Não | Controle aberto e multilíngue |
| IBM Granite 3B | Não | Modelo geral; challenger possível |

O modelo da Principled Intelligence já extrai claims atômicas e decontextualizadas, mas foi treinado para conversas entre usuário e assistente, não especificamente para transcrições médicas em português. Sua taxonomia também não corresponde diretamente à taxonomia GLP-1.

## 4. Primeira etapa recomendada: testar sem treinar

Antes de qualquer fine-tuning, executar um modelo existente e congelado:

```text
Arquivo SRT
    ↓
Limpeza e segmentação
    ↓
Claim Extractor 2B existente
    ↓
Claims estruturadas em JSON
    ↓
Correção e avaliação humana
```

O primeiro candidato é:

```text
principled-intelligence/claim-extractor-2B-q-2605
```

Razões:

- já foi treinado para Claim Extraction;
- permite criar rapidamente um baseline funcional;
- é mais adequado a uma RTX 2060 Super com 8 GB que a versão 4B;
- seus erros reais indicarão o que o fine-tuning do Modelo C precisa corrigir: português, oralidade, contexto, atomicidade, redundância, atribuição ou taxonomia.

O Modelo B deve ser inicialmente mantido sem fine-tuning, para preservar seu papel de baseline comunitário.

## 5. É possível adaptar um modelo ao domínio GLP-1?

Sim. O Modelo C pode ser treinado especificamente para transcrições de vídeos sobre GLP-1:

```text
Modelo Instruct geral
        +
Exemplos anotados: transcrição → claims corretas
        +
SFT com LoRA ou QLoRA
        ↓
Claim Extractor GLP-1 em PT-BR
```

Há duas tarefas diferentes:

1. **Adaptação ao domínio:** transcrições brutas ajudam o modelo a aprender vocabulário, estilo oral e conceitos do domínio.
2. **Aprendizado da tarefa:** pares anotados de entrada e saída ensinam quais claims extrair, como decompor, decontextualizar e estruturar.

Somente treinar com transcrições brutas não ensina Claim Extraction de modo confiável. O treinamento supervisionado precisa de respostas-alvo corretas.

## 6. Relação entre SFT, LoRA, QLoRA, DoRA e few-shot

Esses termos pertencem a camadas diferentes:

| Camada | Técnicas | Função |
|---|---|---|
| Objetivo de aprendizado | SFT, DPO, GRPO | Determina o que será aprendido |
| Atualização eficiente | LoRA, QLoRA, DoRA, QDoRA | Determina como os parâmetros serão adaptados |
| Estratégia de inferência | zero-shot, static few-shot, dynamic few-shot | Determina quais demonstrações entram no prompt |
| Controle da resposta | Pydantic, JSON Schema, enums | Restringe a estrutura da saída |

### SFT

Supervised Fine-Tuning ensina o mapeamento entre a entrada e a resposta humana esperada. É o objetivo apropriado para Claim Extraction.

### LoRA

Congela o modelo-base e treina pequenos adapters de baixo rank. É mais barato que atualizar todos os pesos.

### QLoRA

Mantém o modelo-base congelado e quantizado em 4 bits, enquanto treina adapters em maior precisão. Economiza bastante VRAM.

### DoRA

Decompõe a adaptação em direção e magnitude. Pode superar LoRA em algumas condições, mas custa mais memória e processamento.

### QDoRA

Combina quantização do modelo-base com adapters DoRA. Deve ser tratado como uma ablação posterior, não como o primeiro treinamento.

### Few-shot prompting

Few-shot não treina nem altera os pesos. Exemplos são inseridos temporariamente no prompt para demonstrar a tarefa.

- **Static few-shot:** os mesmos exemplos em todas as entradas.
- **Dynamic few-shot:** exemplos semanticamente semelhantes são recuperados para cada entrada.
- Nome preciso: **Dynamic Few-Shot Claim Extraction with Semantic Example Retrieval**.

Os exemplos recuperáveis devem vir apenas do conjunto de treinamento. Usar exemplos de vídeos de validação ou teste causaria data leakage.

## 7. Modelo-base recomendado para o Modelo C

Para poucos milhares de exemplos, deve-se começar com um modelo **Instruct**, não com um checkpoint Base cru.

### Opção prática para QLoRA

```text
Qwen/Qwen3-4B-Instruct-2507
+ SFT
+ QLoRA
```

Essa opção é adequada para experimentos com memória limitada e possui ecossistema de treinamento maduro.

### Opção Qwen3.5

```text
Qwen/Qwen3.5-4B
+ SFT
+ LoRA FP16/BF16
```

Para Qwen3.5-4B, foi levantado um alerta sobre diferenças de quantização 4-bit acima do normal; por isso, a preferência inicial é LoRA em FP16/BF16 quando houver GPU suficiente. Para 8 GB, um modelo 2B ou Qwen3-4B com QLoRA é mais realista.

### Alternativas

- `Ministral-3-3B-Instruct-2512`: alternativa forte para português e JSON estruturado.
- `HuggingFaceTB/SmolLM3-3B`: controle com maior abertura e reprodutibilidade.
- Granite 3B: challenger opcional.

## 8. Dataset de treinamento

Cada exemplo deve preservar:

- contexto anterior;
- segmento-alvo;
- contexto posterior;
- IDs dos segmentos;
- texto exato usado como evidência;
- lista de claims corretas;
- exemplos negativos com `"claims": []`.

Exemplo conceitual:

```json
{
  "input": {
    "video_id": "video_001",
    "context_before": [
      {"segment_id": 40, "text": "Agora vamos falar da semaglutida."}
    ],
    "target": [
      {"segment_id": 41, "text": "Ela pode causar náusea e vômito no começo."}
    ],
    "context_after": [
      {"segment_id": 42, "text": "Isso costuma melhorar com o tempo."}
    ]
  },
  "output": {
    "claims": [
      {
        "claim": "A semaglutida pode causar náusea no início do tratamento.",
        "source_segment_ids": [40, 41],
        "source_quote": "Ela pode causar náusea",
        "claim_type": "FACTUAL_MEDICAL_CLAIM",
        "topic": "ADVERSE_EVENT",
        "assertion_mode": "ASSERTED",
        "is_atomic": true,
        "is_decontextualized": true
      },
      {
        "claim": "A semaglutida pode causar vômito no início do tratamento.",
        "source_segment_ids": [40, 41],
        "source_quote": "e vômito no começo",
        "claim_type": "FACTUAL_MEDICAL_CLAIM",
        "topic": "ADVERSE_EVENT",
        "assertion_mode": "ASSERTED",
        "is_atomic": true,
        "is_decontextualized": true
      }
    ]
  }
}
```

Exemplo negativo:

```json
{
  "input": {
    "target": [{"segment_id": 98, "text": "Eu acho esse remédio maravilhoso."}]
  },
  "output": {"claims": []}
}
```

## 9. Schema tipado inicial

```python
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field


class ClaimType(str, Enum):
    FACTUAL_MEDICAL_CLAIM = "FACTUAL_MEDICAL_CLAIM"
    FACTUAL_NON_MEDICAL_CLAIM = "FACTUAL_NON_MEDICAL_CLAIM"


class Topic(str, Enum):
    INDICATION = "INDICATION"
    MECHANISM = "MECHANISM"
    DOSAGE = "DOSAGE"
    EFFICACY = "EFFICACY"
    ADVERSE_EVENT = "ADVERSE_EVENT"
    CONTRAINDICATION = "CONTRAINDICATION"
    OFF_LABEL_USE = "OFF_LABEL_USE"
    ACCESS_COST = "ACCESS_COST"
    OTHER = "OTHER"


class AssertionMode(str, Enum):
    ASSERTED = "ASSERTED"
    DENIED = "DENIED"
    HEDGED = "HEDGED"
    ATTRIBUTED = "ATTRIBUTED"


class ExtractedClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim: str
    source_segment_ids: list[int] = Field(min_length=1)
    source_quote: str
    claim_type: ClaimType
    topic: Topic
    assertion_mode: AssertionMode
    is_atomic: bool
    is_decontextualized: bool


class ClaimExtractionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claims: list[ExtractedClaim]
```

O constrained decoding por JSON Schema garante sintaxe, tipos, campos obrigatórios e valores permitidos. Não garante que o enum selecionado esteja semanticamente correto; isso deve ser avaliado contra anotação humana.

## 10. Divisão dos dados

A divisão deve ocorrer por vídeo, antes do chunking:

```text
Vídeos completos
├── Train: 70%
├── Validation: 15%
└── Test: 15%
```

Nenhum chunk de um vídeo pode aparecer em mais de uma partição. O conjunto de teste deve permanecer oculto até a avaliação final.

Quantidade sugerida:

| Quantidade | Finalidade |
|---:|---|
| 100–200 trechos | Piloto técnico e verificação de viabilidade |
| 500–1.000 trechos | Primeiro fine-tuning comparável |
| 2.000–5.000 trechos | Especialização de domínio mais convincente |

## 11. Primeira configuração de treinamento

Recomendação inicial:

```text
Qwen3-4B-Instruct-2507
+ SFT
+ QLoRA 4-bit
+ rank 16
+ JSON Schema na inferência
```

Parâmetros iniciais de referência:

```text
target_modules = all-linear
lora_rank = 16
lora_alpha = 32
lora_dropout = 0.05
epochs = 2
batch_size = 1
gradient_accumulation = 16
learning_rate = 1e-4
max_length = 2048
```

O resultado é um adapter:

```text
Modelo Qwen base
+ adapter QLoRA GLP-1
= Claim Extractor customizado
```

Não começar com full fine-tuning, DPO ou GRPO. Para aprender pares de transcrição e claims humanas corretas, SFT é suficiente; LoRA/QLoRA apenas torna essa adaptação mais econômica.

## 12. Experimentos e ablações

| Configuração | Pesos | Prompt |
|---|---|---|
| C0 | Qwen original | Zero-shot |
| C1 | Qwen original | Static few-shot |
| C2 | Qwen original | Dynamic few-shot |
| C3 | Qwen + SFT/QLoRA GLP-1 | Zero-shot |
| C4 | Qwen + SFT/QLoRA GLP-1 | Dynamic few-shot |
| C5 | Mesmo backbone | SFT + LoRA |
| C6 | Mesmo backbone | SFT + DoRA |

A comparação entre LoRA, QLoRA e DoRA deve usar o mesmo backbone, os mesmos dados, seeds, partições e protocolo de inferência.

## 13. Métricas

Avaliar:

- Atomicity;
- Faithfulness;
- Decontextualization;
- Fluency;
- Focus;
- Coverage;
- \(F_{fact}\);
- Redundancy;
- source-span accuracy;
- macro-F1 dos enums;
- taxa de JSON válido;
- latência;
- VRAM;
- tamanho do adapter.

O constrained decoding pode tornar a taxa de JSON válido próxima de 100%, mas não substitui a avaliação semântica.

## 14. Sequência operacional acordada

1. Selecionar uma transcrição GLP-1 real.
2. Limpar e segmentar o SRT preservando IDs e timestamps.
3. Executar `claim-extractor-2B-q-2605` sem treinamento.
4. Inspecionar manualmente as claims e registrar os erros.
5. Corrigir a saída para iniciar um pequeno conjunto ouro.
6. Avaliar atomicidade, fidelidade, cobertura, redundância, spans e estrutura.
7. Consolidar o guia de anotação e congelar a taxonomia.
8. Anotar mais vídeos e dividir o corpus por vídeo.
9. Treinar o Modelo C com SFT + QLoRA ou LoRA.
10. Comparar A, B e C exatamente nos mesmos vídeos de teste.
11. Executar ablações de few-shot e, posteriormente, LoRA/QLoRA/DoRA.

## 15. Decisão atual

A próxima ação não é treinar imediatamente. Primeiro será testado um Claim Extractor que já existe:

```text
principled-intelligence/claim-extractor-2B-q-2605
```

Depois dos primeiros resultados em uma transcrição real, será possível definir com evidências:

- quais erros precisam ser corrigidos;
- se a versão 4B justifica o custo;
- quais campos do schema são realmente estáveis;
- quanto do ganho pode vir de prompting;
- e quais exemplos devem compor o dataset para o fine-tuning do Modelo C.
