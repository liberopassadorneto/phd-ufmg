# Resumo — Metodologia de Claim Extraction e Benchmark A/B/C

**Projeto:** PhD — Claim Extractor (GLP-1)  
**Escopo:** extração de afirmações factuais de transcrições de vídeos sobre GLP-1 (ex.: semaglutida/Ozempic), antes de classificar veracidade ou desinformação.

## 1. Decisões metodológicas

- Comparar **três modelos de pesos abertos (A, B e C)** nos mesmos transcripts *held-out*.
- Pipeline funcional: **Claim Span Identification → Atomic Claim Decomposition → Claim Normalization → Decontextualization**.
- Avaliar claims por **FEVERFact + Claimify**, com **validação humana** independente.
- **FENICE** é uma análise secundária opcional para correspondência lexical com o *gold standard*, e não substituto de FEVERFact.
- **Faithfulness** mede fidelidade ao que foi dito, não se a informação médica é verdadeira.
- Os estágios da pipeline são requisitos lógicos; alguns modelos geram claims *end-to-end*. Documentar a diferença e não atribuir a cada checkpoint etapas internas que ele não implementa.

## 2. Pipeline do benchmark

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

Os dois frameworks analisam **a saída de cada modelo** sobre o mesmo conjunto de teste.

## 3. Modelos candidatos

| Modelo | Papel | Proposta | Ressalva |
|---|---|---|---|
| **A** | Baseline científico | `Mistral-7B-Instruct-v0.2` com fine-tuning QLoRA de Claim Extraction conforme **FEVERFact** | Reproduzir o ajuste do paper ou obter checkpoint ajustado; o Mistral base não herda automaticamente os resultados publicados. |
| **B** | Comunidade especializada | `principled-intelligence/claim-extractor-4B-q-2605` (Qwen3.5-4B) | Confirmar comportamento em PT-BR e validar claims independentemente do model card. |
| **C** | Domínio GLP-1 | Adaptar o checkpoint B com **SFT/QLoRA** em claims humanos de vídeos GLP-1 | Iniciar do B permite comparar **antes/depois da adaptação de domínio**. Usar Qwen base é outro experimento. |

**B alternativo, apenas complementar:** `Luimas/claim-extractor-detective-qwen3b` (Qwen2.5-3B, QLoRA, **English-only**, JSON com *evidence spans*). Testar em vídeos originalmente em inglês ou como experimento separado de generalização em português. Tradução PT→EN introduz outra variável e não deve ser confundida com inferência nativa.

## 4. Pipeline de Claim Extraction

1. **Claim Span Identification (CSI):** identificar trechos que afirmam algo potencialmente verificável; não converter perguntas, saudações ou chamadas para inscrição em claims.
2. **Atomic Claim Decomposition:** separar cada proposição factual em um claim distinto.
3. **Claim Normalization:** eliminar disfluências, reformular coloquialismos e padronizar termos sem alterar o sentido.
4. **Decontextualization:** resolver pronomes e referências necessárias para entender a afirmação isoladamente.

**Exemplo:**

```text
Transcrição: "A semaglutida reduz o apetite e ela pode causar náusea."

C001 — Semaglutida reduz o apetite.
C002 — Semaglutida pode causar náusea.
```

Preservar `transcript_id`, `claim_id`, `source_span` e timestamps quando existirem. Não corrigir um claim falso usando conhecimento médico externo: isso prejudicaria a fidelidade ao transcript.

## 5. Dataset e protocolo de avaliação

```text
Transcripts + gold claims validados por humanos
                     ↓
       divisão por vídeo / fonte
                     ↓
           Train | Dev | Test
             │      │      │
        treinar C  tuning  benchmark A/B/C
```

- Dividir por **vídeo/fonte**, não por trechos aleatórios, reduzindo risco de vazamento.
- **Não** usar o teste para ajuste de prompts, treinamento ou escolha de hiperparâmetros.
- Para A/B/C, controlar procedimento de chunking, contexto, instruções funcionais, schema de saída, deduplicação e inferência, tanto quanto o suporte de cada modelo permitir.
- Guardar saídas originais e configurações: checkpoint, tokenizer, prompt, quantização, seed e versões.
- Quando arquiteturas de extração diferirem (*end-to-end* vs múltiplas chamadas), concluir sobre **sistemas sob os mesmos requisitos**, não sobre o efeito isolado de uma etapa.

Schema mínimo sugerido:

```json
{
  "transcript_id": "V001",
  "claim_id": "C001",
  "claim": "Semaglutida reduz o apetite.",
  "source_span": "A semaglutida reduz o apetite.",
  "start_timestamp": null,
  "end_timestamp": null
}
```

## 6. Métricas de qualidade de Claim Extraction

### 6.1 FEVERFact — qualidade intrínseca

| Métrica | O que mede | Melhor direção |
|---|---|---|
| **Atomicity** | Uma proposição factual principal por claim | ↑ |
| **Faithfulness** | Fidelidade da afirmação ao transcript, sem invenções | ↑ |
| **Fluency** | Clareza e correção linguística | ↑ |
| **Focus** | Informação extraída relevante, sem excesso | ↑ |
| **Coverage** | Informações relevantes do *gold* recuperadas | ↑ |
| **F_fact** | Média harmônica entre Focus e Coverage | ↑ |
| **Redundancy** | Sobreposição/repetição de informações entre claims | ↓ |

**Métrica agregada principal proposta:**

\[
F_{fact} = \frac{2 \cdot Focus \cdot Coverage}{Focus + Coverage}
\]

Usar a implementação/documentação FEVERFact para cálculo reproduzível; não substituir arbitrariamente Focus/Coverage por contagens binárias ou ROUGE e continuar chamando o resultado de `F_fact` original.

### 6.2 Claimify — critérios complementares

| Métrica | O que mede | Melhor direção |
|---|---|---|
| **Entailment** | A fonte/contexto implica a afirmação extraída? | ↑ |
| **Element-Level Coverage** | Os elementos verificáveis da fonte aparecem nos claims? | ↑ |
| **Decontextualization** | O claim é inteligível e utilizável isoladamente? | ↑ |

**Nota:** Claimify discute atomicidade, mas **Atomicity não é uma métrica central da avaliação proposta no paper**; aqui ela vem de FEVERFact. **Faithfulness** (FEVERFact) e **Entailment** (Claimify) são relacionados, mas seus avaliadores e protocolos diferem.

### 6.3 FENICE — opcional, análise contra gold claims

No estudo FENICE, a qualidade do extrator auxiliar foi medida também por correspondência ROUGE-1 com gold claims humanos:

- `easiness_P`: média, sobre claims gerados, do melhor match ROUGE-1 com algum gold claim;
- `easiness_R`: média, sobre gold claims, do melhor match ROUGE-1 com algum claim gerado;
- `easiness_F1`: média harmônica de `easiness_P` e `easiness_R`.

É **análise secundária**: equivalência semântica entre sinônimos e paráfrases nem sempre é bem capturada por ROUGE-1, particularmente em PT-BR.

## 7. Validação humana e comparação estatística

- Anotar uma amostra de saídas A/B/C com rubricas explícitas para atomicidade, fidelidade, fluência, decontextualização, cobertura e erros de omissão.
- Preferir **dois ou mais anotadores** em parte do corpus; relatar acordo interanotador e divergências resolvidas.
- Checar a aderência dos avaliadores automáticos ao **português brasileiro e domínio GLP-1**, já que modelos de avaliação dos artigos podem ter sido validados prioritariamente em inglês.
- Agregar primeiro **por transcript**, depois calcular macro-médias, para evitar domínio de vídeos longos.
- Comparação **pareada por transcript**; reportar médias, distribuição e intervalos de confiança (ex.: *paired bootstrap*).
- Tratar `F_fact` como indicador agregado primário **sem ocultar quedas em Faithfulness, Atomicity ou Decontextualization**.
- Não construir um score composto misturando todos os indicadores sem justificar pesos, escalas e redundância.

## 8. Questões de pesquisa

- **RQ1:** Qual o desempenho do baseline de pesquisa (A) em transcripts GLP-1?
- **RQ2:** O modelo comunitário especializado (B) supera A nas mesmas condições?
- **RQ3:** A adaptação GLP-1 (C) melhora B, mantendo sua linhagem de checkpoint?
- **RQ4 (complementar):** Quais erros decorrem do português, da oralidade ou do domínio médico?

## 9. Exclusões e decisões em aberto

**Fora do escopo:** Accuracy/Precision/Recall/F1 de **classificação de veracidade**, harmfulness e avaliação de evidência médica externa. Estes pertencem à próxima fase da tese.

**Decidir antes do experimento:**

- disponibilidade/reprodução do checkpoint adaptado de A;
- inicialização exata de C a partir de B;
- política fixa de chunking e deduplicação;
- anotação do gold dataset e amostra humana;
- implementação reprodutível de FEVERFact/Claimify e validação no PT-BR;
- inclusão opcional de B alternativo English-only e de FENICE.

## 10. Referências centrais

1. **Ullrich, Mlynář & Drchal (2025)** — *Claim Extraction for Fact-Checking: Data, Models, and Automated Metrics (FEVERFact).* https://arxiv.org/abs/2502.04955
2. **Metropolitansky & Larson (2025)** — *Towards Effective Extraction and Evaluation of Factual Claims (Claimify).* https://aclanthology.org/2025.acl-long.348/
3. **FENICE (2024)** — *Factuality Evaluation of Summarization Based on Natural Language Inference and Claim Extraction.* https://aclanthology.org/2024.findings-acl.841/
4. **Choi et al. (2021)** — *Decontextualization: Making Sentences Stand-Alone.* https://doi.org/10.1162/tacl_a_00377
5. **Sundriyal et al. (2022)** — *Empowering the Fact-checkers! Automatic Identification of Claim Spans on Twitter.* https://doi.org/10.18653/v1/2022.emnlp-main.525
6. **Min et al. (2023)** — *FActScore: Fine-grained Atomic Evaluation of Factual Precision in Long Form Text Generation.* https://doi.org/10.18653/v1/2023.emnlp-main.741
7. **Sundriyal et al. (2023)** — *From Chaos to Clarity: Claim Normalization to Empower Fact-Checking.* https://doi.org/10.18653/v1/2023.findings-emnlp.439
8. **Deng et al. (2024)** — *Document-level Claim Extraction and Decontextualisation for Fact-Checking.* https://doi.org/10.18653/v1/2024.acl-long.645
9. **Fadda et al. (2026)** — *Generating Knowledge Graphs from News Articles via Multi-Agent Claim Extraction and Attribution.* https://doi.org/10.1016/j.knosys.2026.116890
10. **Community B:** https://huggingface.co/principled-intelligence/claim-extractor-4B-q-2605
11. **Community B alternativo:** https://huggingface.co/Luimas/claim-extractor-detective-qwen3b

---

**Síntese:** comparar Modelos A/B/C sobre os mesmos held-out transcripts, avaliar claims com **FEVERFact + Claimify**, confirmar métricas automáticas por **avaliação humana** e selecionar um extrator confiável antes de avançar para veracidade/desinformação.
