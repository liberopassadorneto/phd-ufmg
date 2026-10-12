# Summary — Golden Dataset e Taxonomia para Desinformação sobre GLP-1

## Contexto do projeto

O projeto de doutorado busca analisar desinformação sobre medicamentos GLP-1, especialmente semaglutida/Ozempic, a partir de **transcrições de vídeos** de plataformas como YouTube e TikTok.

A proposta metodológica discutida neste chat evoluiu de uma classificação simples em nível de vídeo para uma abordagem mais granular em **claim-level misinformation**, mantendo a **transcrição completa como input da LLM**.

---

## 1. O que é claim-level misinformation

`Claim-level misinformation` significa identificar e classificar **cada afirmação factual verificável** presente na transcrição, em vez de rotular todo o vídeo apenas como `MISINFORMATION` ou `NOT_MISINFORMATION`.

Exemplo:

> "Ozempic ajuda a emagrecer. Ele não tem efeitos colaterais importantes. Se quiser emagrecer mais rápido, pode aumentar a dose por conta própria."

Pode ser decomposto em:

1. `Ozempic ajuda a emagrecer.` → `ACCURATE`
2. `Ozempic não tem efeitos colaterais importantes.` → `FALSE` ou `MISLEADING`
3. `É seguro aumentar a dose por conta própria.` → `FALSE`

A vantagem é preservar a granularidade. Um vídeo pode conter simultaneamente claims corretos, enganosos e falsos.

---

## 2. A transcrição completa continua sendo o input

A abordagem claim-level não exige que o input seja apenas uma frase.

O pipeline sugerido é:

```text
TRANSCRIÇÃO COMPLETA
        ↓
      LLM
        ↓
EXTRAÇÃO DE CLAIMS
        ↓
CLASSIFICAÇÃO DE CADA CLAIM
        ↓
VERACIDADE + TÓPICO + TIPO DE ERRO + EVIDÊNCIA + RISCO
```

Assim, o modelo recebe o contexto completo do vídeo, mas o ground truth é anotado em nível de claim.

---

## 3. Frameworks usados em estudos recentes sobre GLP-1/semaglutida

A literatura recente usa diferentes instrumentos para avaliar informação sobre GLP-1. Esses instrumentos **não medem exatamente a mesma coisa**.

### 3.1 Propfe & Seifert — Misrepresentation of semaglutide in social media

Referência:

- Propfe LE, Seifert R. *Misrepresentation of semaglutide in social media*. Naunyn-Schmiedeberg's Archives of Pharmacology. 2026;399:815–832. DOI: `10.1007/s00210-025-04403-5`.

Metodologia:

- 250 posts de Instagram, TikTok, X, Facebook e YouTube.
- Criaram um **Information Score de 0 a 5**.
- Cada post recebia 1 ponto se mencionasse:
  - adverse drug reactions;
  - indicação;
  - mecanismo de ação;
  - escassez;
  - custo do tratamento.

Interpretação:

- Mede **completude/cobertura informacional**, não veracidade.

Resultado importante:

- Aproximadamente 10% dos posts continham informação incorreta.
- Os erros incluíam indicação, mecanismo de ação, efeitos adversos e interações medicamentosas.

Relevância para o projeto:

- Forte inspiração para os tópicos farmacológicos do golden dataset.
- O score de 0–5 pode servir como `information_completeness_score`, mas não como `misinformation_score`.

---

### 3.2 Yeung et al. — Online Information About Side Effects and Safety Concerns of Semaglutide

Referência:

- Yeung AWK et al. *Online Information About Side Effects and Safety Concerns of Semaglutide: Mixed Methods Study of YouTube Videos*. JMIR Infodemiology. 2025;5:e59767. DOI: `10.2196/59767`.

Frameworks utilizados:

- **GQS — Global Quality Score**: 1–5.
- **mDISCERN — Modified DISCERN**: 0–5.
- **Checklist específico de semaglutida**: 12 itens.

GQS mede:

- qualidade global;
- clareza/fluxo;
- utilidade educacional.

mDISCERN mede:

- objetivos claros;
- fontes confiáveis;
- balanceamento;
- referências adicionais;
- discussão de incerteza.

Checklist específico de semaglutida avaliava se o vídeo mencionava, entre outros:

- administração;
- dose segura;
- uso de longo prazo;
- efeitos adversos graves;
- efeitos gastrointestinais;
- contraindicações;
- risco de aspiração;
- falta de dados de longo prazo;
- medicamentos falsificados.

Resultado importante:

- Vídeos longos tiveram GQS, mDISCERN e cobertura de segurança significativamente melhores que Shorts.
- Mesmo conteúdos de fontes de saúde frequentemente omitiam informações críticas.

Relevância:

- Demonstra a utilidade de separar:
  - qualidade global;
  - confiabilidade;
  - cobertura farmacológica específica.

---

### 3.3 Campos-Rivera et al. — Spanish-speaking TikTok videos

Referência:

- Campos-Rivera PA et al. *Quality of information and social norms in Spanish-speaking TikTok videos as levers of commercial practices: The case of semaglutide*. Social Science & Medicine. 2025;366:117646. DOI: `10.1016/j.socscimed.2024.117646`.

Metodologia:

- DISCERN adaptado, escala total aproximada de 15–75.
- Também analisaram normas sociais e narrativas.

Aspectos analisados:

- normalização do uso de semaglutida;
- obesidade como problema individual;
- pharmaceuticalization;
- mudanças de estilo de vida;
- necessidade de orientação profissional.

Resultados:

- baixa qualidade média da informação;
- 71% dos vídeos não mencionavam riscos;
- apenas 11,9% mencionavam ao menos um risco sério.

Relevância:

- Mostra que misinformation pode ocorrer não apenas por uma frase factualmente falsa, mas também por **omissão, narrativa enviesada ou contexto inadequado**.

---

### 3.4 Li, Peng & Wang — Chinese short-video platforms

Referência:

- Li H, Peng F, Wang H. *Quality and reliability of semaglutide-related health information on Chinese short-video platforms: a cross-sectional study of Bilibili and TikTok*. Frontiers in Public Health. 2026;14. DOI: `10.3389/fpubh.2026.1826485`.

Frameworks:

- GQS: 1–5.
- mDISCERN: 0–5.
- JAMA benchmark: 0–4.

JAMA avalia:

- authorship;
- attribution;
- disclosure;
- currency.

Resultados:

- qualidade e confiabilidade moderadas a boas;
- transparência formal inferior;
- conteúdo de profissionais de saúde teve melhor desempenho;
- popularidade não se correlacionou necessariamente com qualidade.

Relevância:

- GQS, mDISCERN e JAMA devem ser vistos como **auxiliary labels**, não como ground truth de veracidade.

---

### 3.5 Günaltay & Kartal — TikTokfluence

Referência:

- Günaltay MM, Kartal N. *TikTokfluence: The rise of GLP-1 receptor agonists in the age of social media health trends*. Journal of the American Pharmacists Association. 2026;66(3):103082. DOI: `10.1016/j.japh.2026.103082`.

Metodologia:

- análise temática qualitativa;
- DISCERN;
- JAMA.

Resultados:

- profissionais de saúde apresentaram maior confiabilidade;
- influencers e indivíduos dominaram o conteúdo;
- likes/views não foram bons indicadores de qualidade.

Relevância:

- reforça que **popularidade ≠ qualidade**.

---

### 3.6 Biçer & Biçer — LLM vs physicians

Referência:

- Biçer Ç, Biçer M. *Quality and Safety of YouTube Videos on GLP-1 Receptor Agonists and Reproductive Health: A Systematic Evaluation Using Validated Instruments and Artificial Intelligence*. JMIR Preprints. 2026:101296. DOI: `10.2196/preprints.101296`.

Status:

- preprint, não peer-reviewed no momento da análise.

Frameworks:

- GQS: 1–5;
- mDISCERN: 0–5;
- JAMA: 0–4;
- Medical Accuracy Scale;
- classificação final `USEFUL` / `MISLEADING`.

Metodologia de IA:

- dois médicos avaliaram os vídeos;
- um LLM avaliou de forma independente;
- comparação humano vs LLM por correlação de Spearman.

Resultados principais:

- forte concordância ordinal:
  - GQS: ρ ≈ 0.845;
  - mDISCERN: ρ ≈ 0.840.
- O LLM tendia a inflar os scores.
- Aproximadamente 22,6% dos vídeos foram classificados como misleading.

Relevância:

- mostra que um LLM pode ser bom para **ranking relativo**, mas não deve ser usado sozinho como ground truth.

---

## 4. Distinções metodológicas importantes

```text
Information/completeness score
        ≠
Quality score
        ≠
Reliability score
        ≠
Veracity score
        ≠
Misinformation label
```

Conclusões principais:

- `LOW QUALITY != FALSE`
- `HIGH QUALITY != TRUE`
- `VERACITY != HARMFULNESS`
- `TOPIC != ERROR TYPE`
- `INSUFFICIENT_EVIDENCE != FALSE`
- Popularidade não deve ser usada como sinal primário de verdade.

---

## 5. Proposta de golden dataset

O golden dataset deve ser anotado por humanos e conter, idealmente, múltiplas camadas.

Estrutura geral:

```text
VIDEO
└── TRANSCRIPT
     ├── CLAIM 1
     ├── CLAIM 2
     ├── CLAIM 3
     └── ...
```

### 5.1 Tabela `videos`

Campos possíveis:

- `video_id`
- `platform`
- `language`
- `video_url`
- `title`
- `published_at`
- `transcript`
- `duration_sec`
- `creator_type`
- `drug_mentions`
- `video_gold_label`
- `gqs`
- `mdiscern`
- `jama`

---

### 5.2 Tabela `claims`

Campos centrais:

- `claim_id`
- `video_id`
- `claim_text`
- `start_char`
- `end_char`
- `claim_type`
- `topic`
- `veracity`
- `misinformation_type`
- `harm_score`
- `evidence_status`
- `annotation_confidence`

Exemplo:

```json
{
  "claim_id": "YT_001_C02",
  "video_id": "YT_001",
  "claim_text": "Ozempic não possui efeitos colaterais importantes.",
  "claim_type": "FACTUAL_MEDICAL_CLAIM",
  "topic": "ADVERSE_EFFECT",
  "veracity": "FALSE",
  "misinformation_type": [
    "FACTUAL_ERROR",
    "RISK_MINIMIZATION"
  ],
  "harm_score": 3,
  "evidence_status": "REFUTED"
}
```

---

## 6. Claim type

Nem toda frase deve ser fact-checked.

Sugestão inicial:

- `FACTUAL_MEDICAL_CLAIM`
- `PERSONAL_EXPERIENCE`
- `OPINION`
- `QUESTION`
- `ADVERTISEMENT`
- `NON_MEDICAL_CLAIM`

Somente `FACTUAL_MEDICAL_CLAIM` deve seguir para classificação de veracidade.

---

## 7. Veracity labels

Sugestão principal:

- `ACCURATE`
- `MISLEADING`
- `FALSE`
- `INSUFFICIENT_EVIDENCE`

### ACCURATE

A evidência científica sustenta adequadamente o claim.

### FALSE

A evidência contradiz claramente o claim.

### MISLEADING

A afirmação contém alguma base factual, mas inclui:

- exagero;
- omissão;
- generalização;
- contexto inadequado;
- distorção de risco/benefício.

### INSUFFICIENT_EVIDENCE

Não há evidência suficiente para confirmar ou refutar de forma segura.

Isso evita tratar ausência de evidência como falsidade.

---

## 8. Tópicos GLP-1 sugeridos

- `INDICATION`
- `MECHANISM_OF_ACTION`
- `EFFICACY_WEIGHT_LOSS`
- `EFFICACY_DIABETES`
- `DOSAGE`
- `TITRATION`
- `ADMINISTRATION`
- `ADVERSE_EFFECT`
- `CONTRAINDICATION`
- `DRUG_INTERACTION`
- `OFF_LABEL_USE`
- `PREGNANCY_REPRODUCTIVE`
- `DISCONTINUATION`
- `WEIGHT_REGAIN`
- `LONG_TERM_USE`
- `LIFESTYLE`
- `COMPOUNDED_SEMAGLUTIDE`
- `COUNTERFEIT_PRODUCT`
- `OTHER`

---

## 9. Tipos de misinformation sugeridos

- `FACTUAL_ERROR`
- `UNSUPPORTED_CLAIM`
- `EXAGGERATION`
- `MISLEADING_OMISSION`
- `CONTEXT_DISTORTION`
- `ANECDOTAL_GENERALIZATION`
- `CAUSAL_OVERCLAIM`
- `RISK_MINIMIZATION`
- `BENEFIT_EXAGGERATION`
- `OUTDATED_INFORMATION`
- `FABRICATED_EVIDENCE`
- `OTHER`

Importante:

- `topic` responde **sobre o que o claim fala**.
- `misinformation_type` responde **como ele está errado ou enganoso**.

---

## 10. Evidence grounding

O golden dataset ideal deve armazenar a evidência usada para determinar a veracidade.

Exemplo:

```text
CLAIM
  ↓
FDA / EMA / ANVISA
RCT
systematic review
clinical guideline
  ↓
SUPPORTS / REFUTES / PARTIALLY_SUPPORTS / INSUFFICIENT
```

Campos possíveis:

- `source_type`
- `source`
- `reference`
- `evidence_passage`
- `relation`

Sugestão de tipos de fonte:

- regulatory document / official label;
- guideline;
- systematic review / meta-analysis;
- randomized controlled trial;
- observational study;
- case report;
- expert opinion.

---

## 11. Harmfulness

Veracidade e risco clínico devem ser separados.

Proposta inicial de escala própria do projeto:

- `0` — nenhum risco clínico relevante;
- `1` — erro de baixo impacto;
- `2` — pode influenciar compreensão ou decisão inadequada;
- `3` — pode levar a uso inseguro do medicamento;
- `4` — potencial de dano clínico grave.

Essa escala precisaria ser formalmente definida no annotation guideline e validada no piloto.

---

## 12. Golden dataset é anotado por humanos

Sim.

Um golden dataset representa o **melhor ground truth disponível**, normalmente criado ou validado por humanos.

Para saúde/farmacologia, o desenho recomendado é:

```text
TRANSCRIÇÃO
    ↓
ANNOTATOR A
    ↓
ANNOTATOR B
    ↓
COMPARAÇÃO
    ↓
DISCORDÂNCIA?
  /        \
NÃO        SIM
 |          |
GOLD    ADJUDICAÇÃO
            ↓
      ESPECIALISTA
            ↓
           GOLD
```

Especialistas possíveis:

- médico;
- farmacêutico;
- pesquisador clínico;
- profissional com experiência relevante em GLP-1.

A LLM pode sugerir labels, mas não deve ser a única fonte do ground truth.

Dataset apenas anotado automaticamente por LLM é mais adequadamente descrito como:

- `silver dataset`;
- `pseudo-labeled dataset`;
- synthetic annotation.

---

## 13. Concordância entre anotadores

O protocolo deve medir inter-annotator agreement.

Métricas candidatas:

- Cohen's κ;
- Krippendorff's α;
- eventualmente ICC para scores ordinais/contínuos.

Discordâncias devem ser analisadas e adjudicadas.

---

## 14. Pilot dataset antes do golden dataset final

Estratégia sugerida:

```text
50–100 vídeos
    ↓
taxonomy v0.1
    ↓
dois anotadores
    ↓
medir concordância
    ↓
identificar labels ambíguos
    ↓
refinar annotation guideline
    ↓
taxonomy v1.0
    ↓
golden dataset completo
```

O piloto deve esclarecer questões como:

- diferença operacional entre `MISLEADING` e `FALSE`;
- quando uma omissão conta como misinformation;
- como tratar experiência pessoal com conselho médico;
- como decompor frases com múltiplos claims;
- quando usar `INSUFFICIENT_EVIDENCE`.

---

## 15. Arquitetura recomendada para o projeto

Versão inicial enxuta:

```text
                    TRANSCRIPT
                        │
                        ▼
                 CLAIM EXTRACTION
                        │
          ┌─────────────┼─────────────┐
          │             │             │
          ▼             ▼             ▼
      VERACITY        TOPIC       ERROR TYPE
          │
  ┌───────┼───────────────┐
  │       │               │
ACCURATE MISLEADING     FALSE
            │
            └──── INSUFFICIENT_EVIDENCE

                        │
                  ┌─────┴─────┐
                  ▼           ▼
              EVIDENCE       HARM
```

Para cada claim, o gold deve responder:

1. Qual é o claim?
2. Qual tópico GLP-1 ele aborda?
3. Qual é sua veracidade?
4. Qual é o tipo de erro, quando aplicável?
5. Qual evidência científica sustenta a classificação?
6. Qual é o potencial de dano?

GQS, mDISCERN e JAMA podem ser adicionados depois como **labels auxiliares em nível de vídeo**.

---

## 16. Contribuição científica potencial

A literatura atual sobre GLP-1 tende a avaliar:

- qualidade do conteúdo;
- confiabilidade;
- transparência;
- cobertura de tópicos;
- presença manual de misinformation;
- Useful/Misleading em nível de vídeo.

Uma contribuição mais avançada seria criar um dataset que combine:

```text
claim-level veracity
+
GLP-1-specific topic taxonomy
+
misinformation/error taxonomy
+
harmfulness
+
evidence grounding
+
human-validated ground truth
```

E depois treinar e avaliar uma LLM para produzir essas dimensões a partir da transcrição completa.

---

## Título sugerido para este chat

**Golden Dataset e Taxonomia para Detecção de Desinformação sobre GLP-1 com LLMs**
