# Resumo — Claim Extractor: benchmark A/B/C e início do Modelo B no WSL

Data: 11/10/2026.

Este documento resume as decisões e propostas discutidas neste chat. Não constitui uma nova verificação dos artigos, modelos ou versões de software. As configurações de execução ainda precisam ser validadas no computador do usuário.

## 1. Objetivo e escopo

Extrair alegações de transcrições de vídeos sobre GLP-1, preservando o significado original e produzindo claims utilizáveis em uma etapa posterior de verificação.

O benchmark aqui trata exclusivamente da qualidade de **Claim Extraction**. Transcrição de áudio, classificação por tópico, veracidade e potencial de dano pertencem a outras etapas.

Uma alegação falsa presente na fonte deve ser extraída fielmente. Faithfulness mede fidelidade à transcrição, não verdade médica.

## 2. Pipeline conceitual

1. **Claim Span Identification:** identificar trechos que expressam alegações.
2. **Atomic Claim Decomposition:** separar proposições compostas.
3. **Claim Normalization:** padronizar a redação sem alterar o significado.
4. **Decontextualization:** resolver referências usando apenas o contexto disponível.

Esses são requisitos conceituais. Usar um extractor generativo pronto não demonstra que ele executa quatro módulos independentes. Essa distinção deve ser registrada no experimento.

## 3. Modelos do benchmark

| Papel | Candidato discutido | Situação |
|---|---|---|
| A — baseline científico | Mistral-7B-Instruct-v0.2 com adaptação/reprodução associada ao FEVERFact | Proposta; confirmar checkpoint, treinamento e protocolo do artigo antes de fixar |
| B — modelo comunitário | principled-intelligence/claim-extractor-4B-q-2605, da linhagem Qwen3.5-4B | Primeiro candidato para piloto local |
| C — modelo do domínio | Backbone aberto, preferencialmente Qwen3.5-4B, com SFT/QLoRA no corpus GLP-1 | Etapa futura; usar apenas o conjunto de treinamento |
| B2 — screening complementar | Luimas/claim-extractor-detective-qwen3b, da linhagem Qwen2.5-3B | Discutido como candidato English-only |

O modelo B2 pode ser testado em português como experimento fora do idioma declarado, em transcrições originalmente em inglês ou com tradução. A tradução adiciona uma variável experimental; seus resultados devem ser separados do benchmark principal em PT-BR.

Os candidatos devem ter pesos acessíveis e licença adequada à reprodução acadêmica. A seleção definitiva continua sujeita à conferência dos repositórios e artigos.

## 4. Protocolo de comparação

- Usar as mesmas transcrições held-out e os mesmos requisitos de extração para A/B/C.
- Fixar segmentação, contexto, parâmetros e protocolo de avaliação antes do teste final.
- Usar trechos de desenvolvimento para ajustar prompts e configurações.
- Separar treino, desenvolvimento e teste por vídeo, evitando vazamento entre segmentos do mesmo vídeo.
- Registrar diferenças inevitáveis de prompt nativo, backend e formato de cada modelo.
- Preservar saídas brutas e distinguir pós-processamento de comportamento do modelo.

## 5. Framework de avaliação acordado

**Transcrições held-out → Modelos A/B/C → Claims gerados → FEVERFact + Claimify → Validação humana → Comparação A/B/C.**

| Métrica/dimensão | Papel acordado no chat | Interpretação |
|---|---|---|
| Atomicity | FEVERFact | Uma proposição principal por claim |
| Faithfulness | FEVERFact | Consistência com a fonte |
| Fluency | FEVERFact | Qualidade linguística |
| Focus | FEVERFact | Foco da saída no conteúdo relevante |
| Coverage | FEVERFact | Recuperação do conteúdo factual de referência |
| F_fact | FEVERFact; agregado principal proposto | Equilíbrio entre Focus e Coverage |
| Redundancy | Diagnóstico complementar discutido com FEVERFact | Repetições entre claims |
| Entailment | Claimify | Fonte implica o claim produzido |
| Element-Level Coverage | Claimify | Cobertura de elementos verificáveis da fonte |
| Decontextualization | Claimify; adaptação ao escopo | Compreensão isolada sem inventar contexto |

As definições e implementações exatas precisam seguir os trabalhos originais. Não substituir os scores por fórmulas improvisadas mantendo o mesmo nome.

### Distinções importantes

- **FEVERFact, FEVER e FENICE são trabalhos diferentes.**
- No fluxo final discutido, **FEVERFact + Claimify** são os frameworks principais.
- Atomicity não deve ser apresentada como uma métrica original do framework Claimify.
- O score original de Decontextualization do Claimify envolve busca de evidências/verificação. Uma avaliação limitada à fonte, para manter o foco na extração, deve ser identificada como **adaptação**, e não como reprodução do score original.
- Faithfulness e Entailment têm proximidade conceitual; sua complementaridade deve ser verificada empiricamente.

### FENICE como análise secundária

Foi discutido o uso opcional de easiness Precision, Recall e F1 para comparar claims gerados com claims humanos por similaridade lexical ROUGE-1. Esse diagnóstico não substitui fidelidade, cobertura granular ou validação humana. O objetivo central do FENICE é avaliar factualidade de resumos.

## 6. Validação humana e resultados

Construir gold claims com evidências textuais e critérios de anotação explícitos. Avaliar uma subamostra em PT-BR e no domínio GLP-1 para verificar a adequação dos avaliadores automáticos.

Verificar especialmente:

- Preservação de negações, quantificadores, números, doses e incertezas.
- Referentes resolvidos corretamente.
- Alegações omitidas, adicionadas ou duplicadas.
- Perguntas e fragmentos sem proposição tratados adequadamente.

Reportar métricas por transcript, macro-average, intervalos de confiança e comparações pareadas. F_fact é o agregado principal proposto, acompanhado dos eixos individuais; ainda não há scores calculados neste chat.

## 7. Hardware informado

| Componente | Configuração |
|---|---|
| Sistema | Windows 11 Pro com WSL; versão WSL2 a confirmar |
| GPU | NVIDIA GeForce RTX 2060 SUPER |
| VRAM dedicada | 8 GB |
| CPU | AMD Ryzen 5 5600X, 6 núcleos |
| RAM | 16 GB |
| SSD | 465,8 GB de capacidade; espaço livre não informado |

Para planejamento, usar os **8 GB dedicados**, sem somar a memória compartilhada do Windows à VRAM.

## 8. Configuração candidata para o primeiro teste

O caminho inicial com Orbitals/vLLM foi revisto após conhecer o hardware. A proposta passou a ser:

| Item | Proposta para validação |
|---|---|
| Ambiente | Ubuntu no WSL2, venv separado |
| Backend | Orbitals com backend Hugging Face/Transformers |
| Quantização | bitsandbytes NF4, 4 bits, double quantization |
| Cálculo | FP16 |
| Atenção | eager como configuração inicial |
| Execução | Uma extração por vez, sem sampling |
| Entrada piloto | Aproximadamente 100–200 palavras |
| Limite de geração | max_new_tokens=1024, ajustável após o teste |

Foram sugeridos PyTorch pelo índice CUDA 12.6 e orbitals[claim-extractor-hf]==0.5.0. Esses pins são o registro da proposta discutida, **não um lockfile validado**. Compatibilidade do modelo, kernels, pacote e GPU ainda precisa ser confirmada.

Não houve execução dessa combinação na máquina do usuário neste chat. Não é possível garantir que o modelo caiba ou rode corretamente apenas pela quantização.

## 9. Diagnóstico que ficou pendente

No PowerShell:

```powershell
wsl --list --verbose
```

No Ubuntu/WSL:

```bash
nvidia-smi
cat /etc/os-release
free -h
```

Após instalar o PyTorch no ambiente virtual:

```python
import torch

print('PyTorch:', torch.__version__)
print('CUDA do pacote:', torch.version.cuda)
print('CUDA disponível:', torch.cuda.is_available())
if torch.cuda.is_available():
    print('GPU:', torch.cuda.get_device_name(0))
    print('Compute capability:', torch.cuda.get_device_capability(0))
    print('VRAM GiB:', torch.cuda.get_device_properties(0).total_memory / 2**30)
```

O WSL usa o driver NVIDIA do Windows; foi orientado não instalar um driver NVIDIA Linux dentro dele. A instalação proposta começou sem CUDA Toolkit separado.

## 10. Uso do modelo comunitário com transcrições

O modelo recebe texto já transcrito; não extrai texto diretamente do áudio.

A interface discutida foi ClaimExtractor, usando o alias claim-extractor-4B-q. O texto seria fornecido como conteúdo de uma mensagem para extração e a saída seria salva em JSON.

No histórico, foram registradas duas características a confirmar no piloto e na versão utilizada:

- Extração da última mensagem, usando mensagens anteriores como contexto.
- Campo evidences existente, mas não preenchido pela versão aberta discutida.

Isso exige testar a adaptação de conversa para transcript. Não assumir que enviar todos os segmentos como uma conversa extrairá claims de todos eles. Não inventar evidence spans ausentes.

Preservar pelo menos transcript_id, texto fonte, hash SHA-256, modelo/revisão, configuração e claims. Timestamps, IDs de segmento e evidências textuais devem ser adicionados quando a segmentação e a proveniência forem implementadas.

## 11. Próximos passos

1. Receber as saídas de diagnóstico e confirmar WSL2/GPU.
2. Validar dependências em um ambiente isolado.
3. Carregar o Modelo B quantizado e medir memória real.
4. Extrair claims de um trecho curto real em PT-BR.
5. Inspecionar saída, idioma, fidelidade e formato.
6. Rodar um piloto de cerca de 10 trechos fora do teste final.
7. Implementar segmentação e proveniência antes de processar vídeos completos.
8. Fixar pesos, código, dependências e parâmetros para o benchmark.

Registrar a variante como **Modelo B — NF4/FP16**. Quantização é uma variável experimental e pode alterar os claims.

## 12. Referências mencionadas na conversa

- [FEVERFact — Claim Extraction for Fact-Checking: Data, Models, and Automated Metrics](https://arxiv.org/abs/2502.04955)
- [Claimify — ACL 2025](https://aclanthology.org/2025.acl-long.348/)
- [FENICE — Findings ACL 2024](https://aclanthology.org/2024.findings-acl.841/)
- [Modelo B — claim-extractor-4B-q-2605](https://huggingface.co/principled-intelligence/claim-extractor-4B-q-2605)
- [Candidato B2 — detective-qwen3b](https://huggingface.co/Luimas/claim-extractor-detective-qwen3b)

Links preservados do histórico; não foram reconsultados para produzir este resumo.

## 13. Estado ao encerrar

Metodologia e caminho inicial de execução propostos. Instalação, carregamento, consumo de VRAM e qualidade dos claims **ainda não confirmados nesta conversa**.

O título sugerido anteriormente foi “05 — Modelo B — Instalação e extração no WSL”; nenhuma renomeação foi realizada.
