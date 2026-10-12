# GLP-1 Misinformation — Taxonomias, Labels e Frameworks para Classificação com LLMs

## Objetivo do chat

Este chat consolidou a literatura científica sobre **desinformação, qualidade da informação e classificação automática de conteúdo sobre semaglutida/Ozempic/GLP-1**, com foco em:

- labels e taxonomias para classificar misinformation;
- scores e frameworks usados para medir qualidade, confiabilidade e completude;
- metodologias de anotação humana;
- uso de IA/LLMs em conteúdo de GLP-1;
- lacunas da literatura;
- proposta de um framework de treinamento e avaliação para um classificador de misinformation em nível de claim.

---

## 1. Conclusão principal

A literatura específica de semaglutida/GLP-1 ainda não possui um framework único e consolidado para treinar um LLM a classificar desinformação em nível de claim.

Os estudos atuais se dividem principalmente em três linhas:

### A. Qualidade e confiabilidade da informação

Frameworks mais usados:

- **GQS — Global Quality Score**
- **DISCERN**
- **modified DISCERN (mDISCERN)**
- **JAMA Benchmark Criteria**

Esses instrumentos medem qualidade, confiabilidade, transparência, equilíbrio e utilidade, mas **não representam diretamente verdade/falsidade**.

### B. Informação específica sobre semaglutida/GLP-1

Os estudos também usam checklists ou taxonomias específicas, cobrindo:

- indicação;
- mecanismo de ação;
- dose;
- administração;
- efeitos adversos;
- contraindicações;
- interações medicamentosas;
- uso off-label;
- segurança;
- efeitos gastrointestinais;
- dados de longo prazo;
- risco de medicamentos falsificados;
- reganho de peso após interrupção;
- custos;
- escassez.

### C. IA/LLM em conteúdo sobre GLP-1

Há trabalhos usando:

- BERT;
- RoBERTa;
- BERTopic;
- GPT-4o-mini;
- GPT-4.1-mini;
- Claude Sonnet.

Entretanto, a maioria usa IA para:

- topic modeling;
- sentiment analysis;
- classificação de uso do medicamento;
- extração de efeitos adversos;
- avaliação automática de qualidade.

Ainda há pouca evidência peer-reviewed de um **LLM treinado especificamente para detectar misinformation sobre GLP-1 em nível de claim com evidence grounding**.

---

# 2. Principais artigos encontrados

## 2.1 Propfe & Seifert — Misrepresentation of semaglutide in social media

**Referência**

Propfe, L. E., & Seifert, R.  
*Misrepresentation of semaglutide in social media.*  
Naunyn-Schmiedeberg's Archives of Pharmacology.  
DOI: `10.1007/s00210-025-04403-5`

### Metodologia

Foram analisados **250 posts**, sendo 50 de cada plataforma:

- Instagram;
- TikTok;
- X;
- Facebook;
- YouTube.

Os autores construíram um **Information Score de 0 a 5**.

Cada post ganhava 1 ponto quando mencionava:

1. adverse drug reactions;
2. drug indication;
3. mechanism of action;
4. supply shortages;
5. treatment costs.

Formalmente:

```text
Information Score =
    adverse_effects
  + indication
  + mechanism
  + shortage
  + cost

score ∈ [0,5]
```

### O que esse score mede

O score mede principalmente **completude informacional**, e não veracidade.

Além disso, os autores avaliaram separadamente a presença de **informação incorreta**.

### Resultados

Média do Information Score por plataforma:

```text
Instagram   0.22 / 5
TikTok      0.72 / 5
X           0.84 / 5
Facebook    1.24 / 5
YouTube     1.38 / 5
```

Foram encontrados conteúdos incorretos em aproximadamente:

```text
24 / 250 ≈ 10%
```

As principais categorias de erro foram:

- indicação;
- mecanismo de ação;
- efeitos adversos;
- interações medicamentosas.

### Relevância para o projeto

Este artigo é uma das melhores bases para uma **taxonomia farmacológica específica de GLP-1**.

Entretanto:

```text
Information Score ≠ Misinformation Score
```

---

# 3. Yeung et al. — Online Information About Side Effects and Safety Concerns of Semaglutide

**Referência**

Yeung, A. W. K. et al.  
*Online Information About Side Effects and Safety Concerns of Semaglutide: Mixed Methods Study of YouTube Videos.*  
JMIR Infodemiology. 2025;5:e59767.  
DOI: `10.2196/59767`

### Amostra

Foram analisados:

```text
96 vídeos completos
93 Shorts
Total = 189
```

### Frameworks utilizados

O estudo combinou:

- GQS;
- modified DISCERN;
- checklist específico de semaglutida.

---

## 3.1 GQS — Global Quality Score

Escala:

```text
1 = very poor
2 = poor
3 = moderate
4 = good
5 = excellent
```

Mede:

- qualidade geral;
- fluxo;
- clareza;
- utilidade educacional.

Não mede diretamente veracidade.

---

## 3.2 Modified DISCERN

Cinco critérios binários:

1. objetivos claros;
2. fontes confiáveis;
3. informação balanceada;
4. fontes adicionais;
5. discussão de incertezas.

```text
Yes = 1
No  = 0

mDISCERN ∈ [0,5]
```

Mede principalmente:

- confiabilidade;
- balanceamento;
- transparência;
- presença de evidência.

---

## 3.3 Checklist específico de segurança da semaglutida

Os autores avaliaram se os vídeos mencionavam:

1. administração;
2. dose segura;
3. uso de longo prazo / mudança de estilo de vida / reganho de peso;
4. efeitos adversos graves;
5. efeitos gastrointestinais;
6. frequência dos efeitos adversos;
7. risco de aspiração em anestesia;
8. contraindicações;
9. meia-vida longa;
10. ausência de dados de longo prazo;
11. alternativas terapêuticas;
12. risco de medicamentos falsificados.

Esse framework é especialmente relevante para o projeto porque aproxima o score de uma **taxonomia de segurança específica para GLP-1**.

### Resultados

Vídeos completos:

```text
GQS       2.6
mDISCERN  2.3
Checklist 2.9
```

Shorts:

```text
GQS       1.1
mDISCERN  1.1
Checklist 0.7
```

Diferenças significativas:

```text
p < .001
```

---

# 4. Campos-Rivera et al. — Quality of information and social norms in Spanish-speaking TikTok videos

**Referência**

Campos-Rivera, P. A. et al.  
*Quality of information and social norms in Spanish-speaking TikTok videos as levers of commercial practices: The case of semaglutide.*  
Social Science & Medicine. 2025;366:117646.  
DOI: `10.1016/j.socscimed.2024.117646`

### Framework

Uso do **DISCERN**, com escala total:

```text
15–75
```

### Resultado

Média:

```text
29.8 / 75
```

indicando baixa qualidade informacional.

### Outros fatores anotados

Além de qualidade, o estudo avaliou narrativas como:

- obesidade como problema individual;
- normalização do uso de semaglutida;
- pharmaceuticalization;
- recomendação do medicamento;
- necessidade de orientação profissional;
- menção ou ausência de riscos.

### Resultados relevantes

- 71% não mencionavam nenhum risco;
- 11,9% mencionavam pelo menos um risco sério;
- aproximadamente metade normalizava o uso;
- 79% enfatizavam emagrecimento sem contextualização adequada de mudanças de estilo de vida.

### Relevância

Esse artigo demonstra que desinformação não precisa ser apenas uma frase falsa.

Existe também:

```text
misleading by omission
```

ou:

```text
risk-benefit distortion
```

---

# 5. Li, Peng & Wang — Semaglutide-related health information on Chinese short-video platforms

**Referência**

Li, H., Peng, F., & Wang, H.  
*Quality and reliability of semaglutide-related health information on Chinese short-video platforms: a cross-sectional study of Bilibili and TikTok.*  
Frontiers in Public Health. 2026;14:1826485.  
DOI: `10.3389/fpubh.2026.1826485`

### Amostra

```text
225 vídeos
107 Bilibili
118 TikTok
```

### Frameworks

#### GQS

```text
1–5
```

#### mDISCERN

```text
0–5
```

#### JAMA Benchmark Criteria

```text
0–4
```

Critérios:

- authorship;
- attribution;
- disclosure;
- currency.

### Resultados

Medianas:

```text
GQS       4 [3–4]
mDISCERN  4 [3–5]
JAMA      2 [1–3]
```

### Inter-annotator agreement

Antes da anotação total, os avaliadores fizeram calibração.

Resultados:

```text
Cohen's κ = 0.59–1.00
ICC       = 0.83–0.94
```

### Insight

```text
boa qualidade percebida
≠
alta transparência científica
```

---

# 6. Sönmez & Fidanci — YouTube videos on semaglutide for weight loss

**Referência**

Güler Sönmez, T., & Fidanci, İ.  
*Cross-sectional analysis of the reliability and engagement metrics of YouTube videos on semaglutide for weight loss.*  
Medicine. 2026;105(23):e49173.  
DOI: `10.1097/MD.0000000000049173`

### Amostra

100 vídeos mais vistos no YouTube relacionados a:

```text
semaglutide weight loss
```

### Frameworks

- GQS;
- modified DISCERN;
- avaliação de scientific accuracy.

### Scientific accuracy

Conteúdo comparado com:

- guidelines de obesidade;
- indicações aprovadas pela FDA;
- principais clinical trials de semaglutida.

### Concordância entre avaliadores

```text
Cohen κ = 0.81
```

### Relevância

Esse paper é particularmente interessante para a futura ideia de:

```text
claim
  ↓
reference evidence
  ↓
scientific accuracy
```

---

# 7. Peng et al. — GLP-1 on TikTok/Bilibili

**Referência**

Peng, G., Wang, C., Zhang, H. W., Xu, T., & Di, J. Z.  
*Assessing the quality and reliability of health information on GLP-1 receptor agonists on TikTok and Bilibili: a cross-sectional analysis of the public health infodemic.*  
Therapeutic Advances in Endocrinology and Metabolism. 2026;17.  
DOI: `10.1177/20420188261467887`

### Frameworks

- mDISCERN;
- GQS;
- JAMA.

Além disso, os autores avaliaram completeness em seis dimensões:

```text
DEFINITION
INDICATIONS
RISK FACTORS
ASSESSMENT
MANAGEMENT
OUTCOMES
```

### Relevância

O artigo mostra uma estrutura multidimensional:

```text
quality
+
reliability
+
transparency
+
content completeness
```

Mas ainda não produz labels de veracidade por claim.

---

# 8. Günaltay & Kartal — TikTokfluence

**Referência**

Günaltay, M. M., & Kartal, N.  
*TikTokfluence: The rise of GLP-1 receptor agonists in the age of social media health trends.*  
Journal of the American Pharmacists Association. 2026;66(3):103082.  
DOI: `10.1016/j.japh.2026.103082`

### Amostra

400 TikToks usando hashtags como:

- #Ozempic;
- #Semaglutide;
- #Mounjaro;
- #Tirzepatide.

### Framework

```text
DISCERN
+
JAMA
+
qualitative thematic analysis
```

### Misinformation

Os autores identificaram conteúdo:

```text
risky
/
misleading
```

principalmente em:

- efeitos adversos;
- uso seguro.

### Resultado

Score de qualidade/confiabilidade:

```text
individual/influencer       34.53
healthcare professional     52.31
```

### Insight

Visualizações e likes não foram bons indicadores de qualidade.

```text
popularity ≠ quality
```

---

# 9. Biçer & Biçer — GLP-1 + reproductive health + LLM

**Referência**

Biçer, Ç., & Biçer, M.  
*Quality and Safety of YouTube Videos on GLP-1 Receptor Agonists and Reproductive Health: A Systematic Evaluation Using Validated Instruments and Artificial Intelligence.*  
JMIR Preprints. 2026:101296.

**Status:** preprint, não peer-reviewed no momento da busca.

### Framework humano

```text
GQS               1–5
mDISCERN           0–5
JAMA               0–4
Medical Accuracy   3 níveis

Final label:
USEFUL
MISLEADING
```

### Uso de LLM

Claude Sonnet:

```text
temperature = 0
```

avaliou os mesmos vídeos sem acesso aos scores humanos.

### Amostra

```text
137 vídeos
```

### Resultados

Classificados como misleading:

```text
31 / 137
22.6%
```

Concordância ordinal entre médicos e LLM:

```text
GQS:
Spearman ρ = 0.845

mDISCERN:
Spearman ρ = 0.840
```

### Problema encontrado

O LLM mostrou:

```text
systematic upward score inflation
```

Ou seja:

- bom ranking relativo;
- calibração imperfeita;
- tendência a avaliar conteúdo de forma mais positiva que os médicos.

### Relevância

Este é atualmente um dos trabalhos mais próximos da ideia:

```text
human annotation
+
medical accuracy
+
misleading/useful label
+
LLM evaluation
```

Mas continua trabalhando principalmente em nível de vídeo.

---

# 10. Sehgal et al. — LLM classifier no domínio GLP-1

**Referência**

Sehgal, N. K. R. et al.  
*Self-Reported Side Effects of Semaglutide and Tirzepatide in Online Communities.*  
medRxiv / arXiv. 2026.

**Status:** preprint.

### Dataset

```text
410,198 Reddit posts
```

### Pipeline

Primeiro:

```text
GPT-4o-mini
    ↓
SELF-USE
vs
NOT SELF-USE
```

Avaliação manual:

```text
Sensitivity = 86%
Specificity = 96%
```

Depois:

```text
GPT-4.1-mini + RAG
    ↓
extract adverse effects
    ↓
map to MedDRA Preferred Term
```

Avaliação:

```text
Recall    = 97%
Precision = 87%
```

### Relevância

Não é misinformation detection.

Porém, demonstra um padrão metodológico diretamente reutilizável:

```text
expert-annotated subset
       ↓
LLM classifier
       ↓
precision
recall
sensitivity
specificity
       ↓
apply to large corpus
```

No projeto, a tarefa poderia ser:

```text
ACCURATE
MISLEADING
FALSE
INSUFFICIENT_EVIDENCE
```

---

# 11. Somani et al. — LLMs e percepção pública sobre GLP-1

**Referência**

Somani et al.  
*Using large language models to assess public perceptions around GLP-1 receptor agonists on social media.*  
Communications Medicine. 2024.  
DOI: `10.1038/s43856-024-00566-z`

### Dataset

Mais de:

```text
390,000 discussões
```

### Métodos

- LLM-assisted topic labeling;
- 168 topics;
- 33 grupos;
- RoBERTa para sentiment.

Labels de sentiment:

```text
NEGATIVE
NEUTRAL
POSITIVE
```

### Relevância

Precedente importante de uso de LLM/NLP em grande escala no domínio de GLP-1, mas não de misinformation.

---

# 12. Javaid et al. — BERTopic/BERT em GLP-1 social media

**Referência**

Javaid et al.  
*Trends in Glucagon-Like Peptide-1 Receptor Agonist Social Media Posts Using Artificial Intelligence.*  
JACC: Advances. 2024.  
DOI: `10.1016/j.jacadv.2024.101182`

### Pipeline

```text
Reddit
  ↓
BERT / BERTopic
  ↓
dimensionality reduction
  ↓
spectral clustering
  ↓
30 topics
  ↓
3 macro-themes
```

Também foi utilizado RoBERTa para sentiment:

```text
-1 = negative
 0 = neutral
+1 = positive
```

### Relevância

É um precedente de:

```text
AI + social media + GLP-1 + human-reviewed labels
```

mas não de misinformation classification.

---

# 13. Diferença entre os principais frameworks

## GQS

Mede:

- qualidade geral;
- clareza;
- fluxo;
- utilidade.

Não mede diretamente veracidade.

```text
LOW GQS ≠ FALSE
HIGH GQS ≠ TRUE
```

---

## DISCERN / mDISCERN

Mede principalmente:

- confiabilidade;
- balanceamento;
- fontes;
- incerteza;
- qualidade da informação terapêutica.

Também não é um truth label.

---

## JAMA

Mede transparência da fonte:

```text
AUTHORSHIP
ATTRIBUTION
DISCLOSURE
CURRENCY
```

Um conteúdo pode ter JAMA baixo e ser factualmente correto.

---

## Semaglutide-specific completeness score

Mede se o conteúdo cobre informações farmacológicas importantes.

Pode ser útil para:

```text
completeness
coverage
omission detection
```

mas não deve ser interpretado como veracidade.

---

# 14. Taxonomia recomendada para o projeto

A proposta consolidada é uma estrutura multidimensional.

## Nível 1 — Tipo de conteúdo

```text
FACTUAL_CLAIM
EXPERIENCE
OPINION
ADVERTISEMENT
NO_MEDICAL_CLAIM
```

---

## Nível 2 — Veracity

```text
ACCURATE
MISLEADING
FALSE
INSUFFICIENT_EVIDENCE
```

### Conversão opcional para binário

```text
ACCURATE
    ↓
NOT_MISINFORMATION

MISLEADING
FALSE
    ↓
MISINFORMATION

INSUFFICIENT_EVIDENCE
    ↓
ABSTAIN
```

---

# 15. Medical topic taxonomy

Sugestão:

```text
INDICATION
MECHANISM_OF_ACTION
EFFICACY_WEIGHT_LOSS
EFFICACY_GLYCEMIC_CONTROL
DOSAGE
TITRATION
ADMINISTRATION
ADVERSE_EFFECT
CONTRAINDICATION
DRUG_INTERACTION
OFF_LABEL_USE
PREGNANCY_REPRODUCTIVE_HEALTH
DISCONTINUATION
WEIGHT_REGAIN
LONG_TERM_USE
LIFESTYLE
COMPOUNDED_SEMAGLUTIDE
COUNTERFEIT_PRODUCT
ACCESS_SHORTAGE
COST
```

---

# 16. Misinformation error taxonomy

Sugestão multidimensional:

```text
FACTUAL_ERROR
EXAGGERATION
OMISSION
CONTEXT_DISTORTION
ANECDOTAL_GENERALIZATION
CAUSAL_OVERCLAIM
UNSUPPORTED_CLAIM
OUTDATED_INFORMATION
FABRICATED_EVIDENCE
RISK_BENEFIT_DISTORTION
DOSAGE_ERROR
INDICATION_ERROR
MECHANISM_ERROR
ADVERSE_EFFECT_ERROR
ADVERSE_EFFECT_OMISSION
CONTRAINDICATION_ERROR
CONTRAINDICATION_OMISSION
DRUG_INTERACTION_ERROR
OFF_LABEL_MISREPRESENTATION
POPULATION_MISAPPLICATION
PREGNANCY_REPRODUCTIVE_ERROR
DISCONTINUATION_ERROR
PRODUCT_IDENTITY_ERROR
```

---

# 17. Harmfulness

Veracidade e risco clínico devem ser dimensões independentes.

Sugestão:

```text
0 = sem dano clínico relevante
1 = dano muito baixo
2 = pode influenciar decisão inadequada
3 = pode levar a uso inseguro
4 = potencial para dano clínico grave
```

Exemplo:

```text
Claim A:
"Semaglutida foi aprovada no ano X."

FALSE
harm = 0
```

versus:

```text
Claim B:
"Dobre sua dose para emagrecer mais rápido."

FALSE
DOSAGE_ERROR
harm = 4
```

---

# 18. Evidence grounding

O modelo não deve classificar apenas com base na memória interna.

Pipeline recomendado:

```text
CLAIM
  ↓
EVIDENCE RETRIEVAL
  ↓
FDA / EMA / ANVISA
RCTs
systematic reviews
meta-analyses
guidelines
drug labels
  ↓
CLAIM × EVIDENCE COMPARISON
  ↓
VERACITY LABEL
```

Possíveis evidence stance labels:

```text
SUPPORTS
CONTRADICTS
PARTIALLY_SUPPORTS
INSUFFICIENT_EVIDENCE
```

---

# 19. Proposta de registro por claim

Exemplo:

```json
{
  "claim_id": "video_001_claim_03",
  "claim": "Ozempic praticamente não tem efeitos colaterais.",
  "claim_type": "FACTUAL_CLAIM",
  "topic": "ADVERSE_EFFECT",
  "veracity": "MISLEADING",
  "misinformation_type": [
    "ADVERSE_EFFECT_OMISSION",
    "RISK_BENEFIT_DISTORTION"
  ],
  "harm_score": 3,
  "evidence_stance": "CONTRADICTS",
  "evidence_quality": 5,
  "human_confidence": 0.95
}
```

---

# 20. Papel de GQS, DISCERN e JAMA no projeto

Esses scores podem ser usados como **atributos auxiliares do vídeo/documento**, e não como labels principais de misinformation.

Estrutura sugerida:

```text
VIDEO
 ├── GQS
 ├── mDISCERN
 ├── JAMA
 ├── completeness
 └── CLAIMS
       ├── veracity
       ├── topic
       ├── error_type
       ├── harmfulness
       └── evidence
```

---

# 21. Pesquisa gap identificada

A literatura atual oferece separadamente:

```text
QUALITY / RELIABILITY
    ↓
GQS
DISCERN
JAMA
```

e:

```text
GLP-1 SPECIFIC CONTENT
    ↓
indication
mechanism
adverse effects
contraindications
interactions
safety
...
```

e:

```text
AI / LLM
    ↓
BERT
RoBERTa
BERTopic
GPT
Claude
```

Mas ainda falta, de forma consolidada:

```text
GLP-1 CLAIM
    ↓
EVIDENCE RETRIEVAL
    ↓
SCIENTIFIC EVIDENCE
    ↓
LLM CLASSIFIER
    ↓
VERACITY
ERROR TYPE
HARMFULNESS
EVIDENCE QUALITY
CALIBRATED CONFIDENCE
```

Especialmente em nível de **claim**.

---

# 22. Possível contribuição científica do projeto

Uma formulação possível:

> Desenvolver e validar uma taxonomia multidimensional e um modelo baseado em LLM para identificação de desinformação sobre medicamentos GLP-1 em conteúdo de redes sociais, combinando veracidade em nível de claim, tipos específicos de erro farmacológico, risco clínico e evidence grounding.

Essa abordagem vai além de classificar um vídeo inteiro como:

```text
FAKE
/
TRUE
```

e permite perguntar:

- o claim é verdadeiro?
- qual o tipo de erro?
- qual tópico médico está envolvido?
- existe omissão?
- qual o risco clínico?
- qual evidência sustenta o label?
- quando o modelo deveria se abster?
- o modelo está calibrado?
- qual tipo de misinformation ele detecta melhor?

---

# 23. Framework consolidado sugerido

```text
                 VIDEO TRANSCRIPT
                       │
                       ▼
             CLAIM EXTRACTION
                       │
                       ▼
                ATOMIC CLAIM
                       │
          ┌────────────┼─────────────┐
          ▼            ▼             ▼
       TOPIC       VERACITY      ERROR TYPE
                       │
        ┌──────────────┼───────────────┐
        ▼              ▼               ▼
    ACCURATE       MISLEADING         FALSE
                       │
                       ▼
              EVIDENCE RETRIEVAL
                       │
                       ▼
          FDA / EMA / ANVISA / RCT
        systematic review / guideline
                       │
            ┌──────────┴──────────┐
            ▼                     ▼
       HARM SCORE          EVIDENCE QUALITY
            │
            ▼
       MODEL CONFIDENCE
            │
            ▼
      HUMAN VALIDATION
```

---

# 24. Referências-chave para a tese

1. Propfe, L. E., & Seifert, R.  
   *Misrepresentation of semaglutide in social media.*  
   DOI: `10.1007/s00210-025-04403-5`

2. Yeung, A. W. K. et al.  
   *Online Information About Side Effects and Safety Concerns of Semaglutide: Mixed Methods Study of YouTube Videos.*  
   DOI: `10.2196/59767`

3. Campos-Rivera, P. A. et al.  
   *Quality of information and social norms in Spanish-speaking TikTok videos as levers of commercial practices: The case of semaglutide.*  
   DOI: `10.1016/j.socscimed.2024.117646`

4. Li, H., Peng, F., & Wang, H.  
   *Quality and reliability of semaglutide-related health information on Chinese short-video platforms.*  
   DOI: `10.3389/fpubh.2026.1826485`

5. Güler Sönmez, T., & Fidanci, İ.  
   *Cross-sectional analysis of the reliability and engagement metrics of YouTube videos on semaglutide for weight loss.*  
   DOI: `10.1097/MD.0000000000049173`

6. Peng, G. et al.  
   *Assessing the quality and reliability of health information on GLP-1 receptor agonists on TikTok and Bilibili.*  
   DOI: `10.1177/20420188261467887`

7. Günaltay, M. M., & Kartal, N.  
   *TikTokfluence: The rise of GLP-1 receptor agonists in the age of social media health trends.*  
   DOI: `10.1016/j.japh.2026.103082`

8. Biçer, Ç., & Biçer, M.  
   *Quality and Safety of YouTube Videos on GLP-1 Receptor Agonists and Reproductive Health.*  
   JMIR Preprints, 2026.

9. Somani et al.  
   *Using large language models to assess public perceptions around GLP-1 receptor agonists on social media.*  
   DOI: `10.1038/s43856-024-00566-z`

10. Javaid et al.  
    *Trends in Glucagon-Like Peptide-1 Receptor Agonist Social Media Posts Using Artificial Intelligence.*  
    DOI: `10.1016/j.jacadv.2024.101182`

11. Sehgal, N. K. R. et al.  
    *Self-Reported Side Effects of Semaglutide and Tirzepatide in Online Communities.*  
    medRxiv / arXiv, 2026.

---

## Resumo final

A literatura específica de GLP-1 já possui bons instrumentos para medir:

- qualidade;
- confiabilidade;
- transparência;
- completude;
- segurança;
- informação farmacológica.

Também existem precedentes recentes de uso de LLMs para análise e classificação de conteúdo sobre GLP-1.

Porém, continua existindo espaço para um framework que una:

```text
claim-level veracity
+
GLP-1-specific taxonomy
+
misinformation error type
+
harmfulness
+
scientific evidence grounding
+
LLM confidence/calibration
```

Esse é o principal research gap identificado neste chat.
