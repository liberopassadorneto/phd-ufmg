principled-intelligence| Candidato | Texto esperado | Claim Extraction | Limitações | Recomendação |
|---|---|---|---|---|
| [Gemma-2B-APS](https://huggingface.co/google/gemma-2b-aps-it) | Passagens de texto livre | Decompõe todas as frases em proposições simples e autocontidas | English-only; não seleciona apenas claims relevantes | **Melhor candidato científico para B** |
| [Gemma-7B-APS](https://huggingface.co/google/gemma-7b-aps-it) | Passagens de texto livre | Mesmo método, com maior capacidade | Mais pesado; licença Gemma | Referência de maior porte |
| [detective-qwen3b](https://huggingface.co/Luimas/claim-extractor-detective-qwen3b) | Notícia, post social, review, press release | Claims atômicos, tipos, stance, evidência textual e JSON | English-only; aproximadamente 4.000 caracteres; validação comunitária | **Melhor candidato de engenharia** |
| [NewsScope-Llama-3.1-8B](https://huggingface.co/nidhipandya/NewsScope-lora) | Artigos completos, inclusive saúde | Claims verificáveis e `evidence_from_article` | Produz somente 2–3 claims; 8B; licença Llama | Bom baseline document-level |
| [Babelscape T5 Claim Extractor](https://huggingface.co/Babelscape/t5-base-summarization-claim-extractor) | Resumos e textos curtos | Claims atômicos | English-only; treinado para summaries | Baseline pequeno/científico |
| [ClaimPT/BERTimbau](https://huggingface.co/lfcc/bert-claimpt-chunk) | Notícias em português | Detecta spans contendo claims | Não atomiza, normaliza ou decontextualiza | Útil somente para CSI em português |


| Rank | Modelo | Downloads/mês | Likes | Entrada principal | Adequação ao transcript |
|---:|---|---:|---:|---|---|
| 1 | [`Babelscape/t5-base-summarization-claim-extractor`](https://huggingface.co/Babelscape/t5-base-summarization-claim-extractor) | **29.207** | **16** | Summary/texto condensado | Média |
| 2 | [`google/gemma-7b-aps-it`](https://huggingface.co/google/gemma-7b-aps-it) | **465** | **46** | Passagens de texto livre | Alta |
| 3 | [`Luimas/claim-extractor-detective-qwen3b`](https://huggingface.co/Luimas/claim-extractor-detective-qwen3b) | **410–415** | **4** | Notícias, posts, reviews e prosa livre | **Muito alta** |
| 4 | [`principled-intelligence/claim-extractor-4B-q-2605`](https://huggingface.co/principled-intelligence/claim-extractor-4B-q-2605) | **159** | **6** | Conversações | Baixa/média |
| 5 | [`dongyru/Mistral-7B-Claim-Extractor`](https://huggingface.co/dongyru/Mistral-7B-Claim-Extractor) | **122** | **4** | Não documentada | Incerta |
| 6 | [`principled-intelligence/claim-extractor-2B-q-2605`](https://huggingface.co/principled-intelligence/claim-extractor-2B-q-2605) | **116** | **6** | Conversações | Baixa/média |
| 7 | [`google/gemma-2b-aps-it`](https://huggingface.co/google/gemma-2b-aps-it) | **63** | **22** | Passagens de texto livre | **Alta** |
| 8 | [`varadhbhatnagar/fc-claim-det-T5-base`](https://huggingface.co/varadhbhatnagar/fc-claim-det-T5-base) | **19** | **2** | Claim social já identificada | Baixa |
| 9 | [`nidhipandya/NewsScope-lora`](https://huggingface.co/nidhipandya/NewsScope-lora) | **11** | **0** | Artigos jornalísticos | Média |
| 10 | [`SAGESSE-EPFL/Mistral-7b-claims-extraction`](https://huggingface.co/SAGESSE-EPFL/Mistral-7b-claims-extraction) | **3** | **0** | Comentários do Reddit | Média |


| Rank | Repositório | Stars | Papel |
|---:|---|---:|---|
| 1 | [`Babelscape/FENICE`](https://github.com/Babelscape/FENICE) | **31** | Avaliação factual com Claim Extractor T5 |
| 2 | [`Principled-Intelligence/orbitals`](https://github.com/Principled-Intelligence/orbitals) | **23** | SDK dos ClaimExtractor 2B/4B |
| 3 | [`Tswings/AVeriTeC-DCE`](https://github.com/Tswings/AVeriTeC-DCE) | **19** | Pipeline document-level multimodelo |
| 4 | [`varadhbhatnagar/FC-Claim-Det`](https://github.com/varadhbhatnagar/FC-Claim-Det) | **4** | Normalização/sumarização de claims sociais |
| 5 | [`aic-factcheck/claim_extraction`](https://github.com/aic-factcheck/claim_extraction) | **1** | Código e métricas do FEVERFact |
| 6 | [`nidhip1611/NewsScope`](https://github.com/nidhip1611/NewsScope) | **0** | Extração de 2–3 claims de notícias |
| 7 | [`man-in-deep/FACT-AI`](https://github.com/man-in-deep/FACT-AI) | **0** | Implementação comunitária inspirada no Claimify | ([GitHub][1])

[1]: https://github.com/Babelscape/FENICE?utm_source=chatgpt.com "GitHub - Babelscape/FENICE: FENICE (Factuality Evaluation of Summarization based on Natural Language Inference and Claim Extraction) is a factuality-oriented metric for summarization."

- Mistral-7B-Instruct-v0.2: `mistralai/Mistral-7B-Instruct-v0.2`
