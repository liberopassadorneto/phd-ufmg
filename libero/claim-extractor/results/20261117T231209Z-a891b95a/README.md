# Resultados de extração de claims — Cuba

Execução iniciada em 17/11/2026, às 23:12:09 UTC, concluída em 18/11/2026.
Os resultados originais foram copiados sem modificar ou reparar as respostas.

- `inputs.json`: transcrições normalizadas, caminhos e hashes das entradas por modelo. Inglês para os geradores e português para ClaimPT.
- `summary.json`: resumo das métricas e estados dos 12 modelos selecionados originalmente.
- `<modelo>/output.raw` ou `output.json`: resposta nativa. JSON incompleto foi preservado como recebido.
- `<modelo>/processing.json`: configuração efetiva, tempo e uso de recursos.

Foram concluídas tentativas de 11 modelos: seis `success` e cinco `partial`.
NewsScope foi interrompido por decisão do usuário após fallback lento para RAM;
seu registro aparece como `failed`, sem saída. Foi excluído das execuções futuras de `all`.

Esta execução começou antes das otimizações posteriores do executor: inclui
verificação SHA-256 e testes prévios de CUDA/NF4. Os tempos representam o
comportamento daquela execução; não medem o executor já otimizado. Médias de
RAM/VRAM adicionadas posteriormente não estão disponíveis nestes registros.

## Resultado observado por modelo

Revisão manual comparando as respostas com a transcrição; não há referência
anotada, pontuação automática nem validação da veracidade médica das afirmações.
A qualidade abaixo refere-se à fidelidade ao texto de entrada. `success` indica
conclusão técnica, não correção semântica. Os formatos e protocolos diferem entre modelos.

| Modelo | Estado | Total (s) | Inferência (s) | VRAM pico (GiB) | RAM pico (GiB) | Resultado observado |
|---|---|---:|---:|---:|---:|---|
| [Principled 4B](principled-4b/output.json) | success | 328,078 | 182,162 | 5,531 | 10,711 | Melhor saída estruturada nesta revisão qualitativa: JSON válido, 28 claims, boa cobertura e frases compreensíveis isoladamente. Algumas claims agrupam várias informações. |
| [Gemma 7B](gemma-7b-aps/output.raw) | success | 301,009 | 94,525 | 5,971 | 7,419 | Boa cobertura, 51 proposições. Inclui perguntas, fragmentos e repetições que não constituem claims úteis. |
| [Babelscape T5](babelscape-t5/output.raw) | success | 47,327 | 9,580 | 1,273 | 1,454 | Resposta concisa e geralmente fiel, mas omite nomes dos medicamentos e parte das recomendações de estilo de vida. |
| [Gemma 2B](gemma-2b-aps/output.raw) | success | 145,962 | 44,279 | 4,936 | 5,339 | Boa cobertura, 51 proposições, com fragmentos sem sujeito e redundâncias. |
| [Principled 2B](principled-2b/output.json) | success | 164,503 | 92,032 | 5,328 | 7,586 | JSON válido, 30 claims, mas contém uma inversão grave de sentido: afirma que obesidade pode ser curada, contrariando a entrada. |
| [ClaimPT](claimpt/output.json) | success | 30,682 | 0,292 | 0,551 | 1,027 | Saída de classificação de tokens, não lista textual de claims. O argmax dos logits classificou os 431 tokens como `O`; nenhuma claim identificada por esse critério. |
| [Detective Qwen3B](detective-qwen3b/output.json) | partial | 168,021 | 79,853 | 6,326 | 4,403 | Cortado no limite de 768 tokens, JSON inválido; inventa uma data de publicação e repete perguntas genéricas de verificação. |
| [Dongyru Mistral](dongyru-mistral/output.raw) | partial | 220,608 | 3,960 | 4,471 | 5,724 | Uma tripla semanticamente incorreta, atribuindo sobrepeso e comorbidade às próprias canetas. Resposta mínima sob orçamento herdado muito curto. |
| [FC-Claim-Det T5](fc-claim-det-t5/output.raw) | partial | 34,573 | 1,071 | 1,229 | 1,910 | Uma frase resumida, sem cobertura do restante da transcrição; atingiu `max_length=15`. |
| [SAGESSE Mistral](sagesse-mistral/output.json) | partial | 504,396 | 5,038 | 4,668 | 5,738 | Apenas o início da primeira claim, com JSON incompleto. |
| [Mistral Instruct v0.2](mistral-instruct-v02/output.raw) | partial | 329,223 | 4,652 | 4,471 | 5,694 | Uma frase e o início da seguinte; resposta incompleta. |
| [NewsScope](newsscope/processing.json) | failed / interrompido | 1394,167 | 0,000 | 6,793 | 19,051 | NF4 falhou por falta de memória durante o carregamento do adaptador. A tentativa com RAM foi interrompida pelo usuário devido à lentidão. |

## Problemas concretos encontrados

**Principled 2B:** gerou `Obesity is a chronic disease that can be cured.` A entrada
contém `Even after losing weight, you will not be cured`. Há inversão do sentido.

**Detective:** gerou `publication_date: 2023-09-07`, informação ausente na entrada.
O JSON termina no meio de uma lista de perguntas e não pode ser analisado como
um documento completo.

**Gemma 2B/7B:** incluem perguntas de abertura e a expressão isolada
`Weight-loss pens.` como proposições. O Gemma 2B também produz fragmentos como
`sold under the brand name Saxenda.` O Gemma 7B explicita melhor os sujeitos
nesse trecho.

**ClaimPT:** os logits foram inspecionados com argmax por token, usando o
mapeamento do checkpoint: `0=O`, `1=B-Claim`, `2=I-Claim`, `3=B-Non-claim`,
`4=I-Non-claim`. Todos os 431 tokens receberam a classe 0. Nenhum pós-processamento
foi aplicado ao arquivo original.

**Limites de geração:** Dongyru, SAGESSE e Mistral Instruct herdaram
`max_length=20` e `max_new_tokens=null`; suas respostas muito curtas impedem
uma comparação adequada da capacidade de extração. FC-T5 usou
`max_length=15` e Detective usou `max_new_tokens=768`. Essas configurações estão
registradas nos respectivos `processing.json`. Uma nova avaliação com orçamento
explícito é necessária antes de descartar esses modelos por qualidade.

## Conclusão provisória

Principled 4B e Gemma 7B são os candidatos prioritários para revisão anotada.
Babelscape merece comparação quando a concisão e o custo forem importantes.
Esta observação vale somente para a transcrição analisada e não estabelece um
ranking geral dos modelos. Não foram alterados prompts, parâmetros ou saídas
para produzir esta revisão.
