# Resumo — Gemma-APS: instalação, inferência e teste em transcript GLP-1

**Projeto:** PhD — Claim Extractor  
**Modelo testado:** `google/gemma-2b-aps-it`  
**Papel proposto:** candidato ao Modelo A (baseline científico de Abstractive Proposition Segmentation)  
**Data do teste:** 10 de outubro de 2026

## 1. Objetivo

Testar um modelo open-weight, associado a trabalho científico, que execute Claim Extraction generativa em texto livre. O primeiro candidato escolhido foi o `google/gemma-2b-aps-it`, ajustado especificamente para **Abstractive Proposition Segmentation (APS)** — decomposição de uma passagem em fatos, afirmações e ideias individuais.

Referências:

- Model card: <https://huggingface.co/google/gemma-2b-aps-it>
- Artigo: *Scalable and Domain-General Abstractive Proposition Segmentation* — <https://arxiv.org/abs/2406.19803>
- Documentação do `uv`: <https://docs.astral.sh/uv/>

## 2. Decisão após a tentativa com o modelo Detective

A primeira tentativa usou `Luimas/claim-extractor-detective-qwen3b` por meio de `llama-cpp-python` com CUDA. A RTX 2080 foi detectada, mas o wheel pré-compilado encerrou com `Illegal instruction` porque o servidor possui um Xeon E5620 sem AVX. Compilar uma versão própria exigiria um CUDA Toolkit completo e uma build sem AVX.

O model card do Detective também oferecia uma rota com Transformers, mas decidiu-se reiniciar os testes pelo candidato científico mais relevante: Gemma-APS. Essa rota usa PyTorch/Transformers e funcionou no hardware existente, sem `llama-cpp-python`, `nvcc` ou compilação customizada.

## 3. Hardware efetivamente utilizado no servidor

- CPU: Intel Xeon E5620 2.40 GHz
- Instruções disponíveis: até SSE4.2; sem AVX, AVX2, FMA ou F16C
- GPU: NVIDIA GeForce RTX 2080
- VRAM: 8 GB (aproximadamente 7.968 MiB livres antes do teste)
- Sistema: Linux no servidor `cuba`
- Python: 3.10
- Gerenciador do projeto: `uv`

> Este servidor é diferente da máquina pessoal com RTX 2060 SUPER mencionada em outros testes do projeto.

## 4. Estrutura do projeto

```text
/home/libero_neto/claim_extractor/models/gemma-2b-aps-it/
├── input/
│   └── automatic.en.txt
├── output/
│   └── automatic.en.claims.json
├── src/
│   └── inference.py
├── pyproject.toml
├── uv.lock
└── .venv/
```

O `inference.py` não é um arquivo oficial do modelo. É um runner experimental próprio, baseado no snippet publicado no model card.

## 5. Configuração com `uv`

O projeto foi administrado com a interface de projetos do `uv`, evitando misturar `pip` tradicional e chamadas diretas a `.venv/bin/python`.

Inicialização:

```bash
uv init --bare --python 3.10
```

PyTorch CUDA 12.4:

```bash
uv add \
  "torch==2.6.0" \
  --index pytorch-cu124=https://download.pytorch.org/whl/cu124
```

Dependências:

```bash
uv add \
  "transformers>=4.42,<5" \
  "accelerate>=0.26,<2" \
  "huggingface-hub>=0.23,<2" \
  "nltk>=3.8,<4" \
  "numpy>=1.26,<3"
```

Dados do NLTK:

```bash
uv run python -m nltk.downloader punkt punkt_tab
```

## 6. Validação do PyTorch e da GPU

O teste confirmou:

```text
PyTorch: 2.6.0+cu124
CUDA do PyTorch: 12.4
CUDA disponível: True
GPU: NVIDIA GeForce RTX 2080
Compute capability: (7, 5)
Teste FP16: [2.0, 4.0]
```

Apesar de `torch.cuda.is_bf16_supported()` ter retornado `True`, a inferência foi mantida em FP16, pois a operação FP16 foi validada diretamente e é adequada à RTX 2080.

## 7. Autenticação no Hugging Face

O repositório Gemma é público, mas exige aceitação da licença. A conta `lpassador` aceitou os termos e autenticou um token de leitura:

```bash
uv run hf auth login
uv run hf auth whoami
```

O acesso foi verificado baixando apenas o `config.json` antes dos pesos:

```bash
uv run hf download google/gemma-2b-aps-it config.json
```

Revisão utilizada e fixada no runner:

```text
6526315a71d38bfbde56357466ddcc27629cfd78
```

## 8. Input e output recomendados pelo model card

O input oficial é uma passagem em inglês dividida em sentenças. Cada sentença é delimitada por `<s>` e `</s>` e as sentenças são separadas por quebra de linha.

Exemplo:

```text
<s> Semaglutide reduces appetite. </s>
<s> It can delay gastric emptying. </s>
```

O conteúdo é enviado como mensagem de usuário ao chat template:

```python
messages = [
    {
        "role": "user",
        "content": propositions_input,
    }
]
```

Saída bruta esperada:

```text
PROPOSITIONS:
<s>
- Semaglutide reduces appetite.
</s>
<s>
- Semaglutide can delay gastric emptying.
</s>
```

Cada grupo de saída corresponde a uma sentença de entrada. O modelo não retorna nativamente JSON, `claim_id`, timestamps, tópico, tipo, veracidade, harmfulness ou confiança.

## 9. Smoke tests

### 9.1 Exemplo oficial

O exemplo sobre Sarah Stage e James Hunter reproduziu o resultado esperado no model card. O pico de memória foi de aproximadamente 4,73 GiB.

### 9.2 Exemplo curto no domínio GLP-1

Input:

```text
Semaglutide is a GLP-1 receptor agonist approved for the treatment of type 2 diabetes. It can also reduce appetite and delay gastric emptying. Some online videos claim that semaglutide causes permanent weight loss without dietary changes.
```

O modelo:

- separou as sentenças em claims atômicos;
- resolveu o pronome `It` como `Semaglutide`;
- preservou a atribuição `Some online videos claim...`, sem apresentar a alegação como fato;
- utilizou aproximadamente 4,73 GiB de VRAM.

## 10. Preparação do transcript `.srt`

O arquivo original `automatic.srt` estava em português, possuía 53 legendas e duração aproximada de 2min31s. Como o Gemma-APS é oficialmente English-only, o transcript foi traduzido para inglês antes da inferência.

Correções evidentes de ASR realizadas durante a preparação:

- `egóvio` → `Wegovy`
- `eemppique` → `Ozempic`
- `tirepatida` → `tirzepatide`
- `monjar` → `Mounjaro`
- remoção do filler final `Yeah`

Artefatos preparados:

- `automatic.en.txt`: passagem limpa e traduzida;
- `automatic.en.aps-input.jsonl`: sete prompts congelados, cada um com até três sentenças no formato `<s>...</s>`.

Para comparações A × B × C, a tradução deve ser congelada e reutilizada por todos os modelos. A tradução é uma variável adicional do experimento e deve ser documentada.

## 11. Runner experimental

O `src/inference.py` foi criado especificamente para o benchmark. Ele preserva os elementos centrais do model card:

- `AutoTokenizer`;
- `AutoModelForCausalLM`;
- `apply_chat_template`;
- marcadores `<s>...</s>`;
- `do_sample=False`;
- pós-processamento dos grupos de proposições.

Funcionalidades adicionais do runner:

- leitura de `.txt` e `.srt`;
- separação de sentenças com NLTK;
- divisão em lotes pequenos;
- execução em FP16;
- saída estruturada em JSON;
- `claim_id` sequencial;
- vínculo entre claim, chunk e sentença de origem;
- hash SHA-256 do input;
- revisão fixa do modelo;
- tempo de carregamento e inferência;
- medição de VRAM.

O runner é infraestrutura própria; não deve ser descrito como código oficial do Gemma-APS.

## 12. Comando de inferência

```bash
cd /home/libero_neto/claim_extractor/models/gemma-2b-aps-it

uv run python src/inference.py \
  input/automatic.en.txt \
  --language en \
  --sentences-per-chunk 3 \
  --max-new-tokens 512 \
  --output output/automatic.en.claims.json
```

Fluxo executado:

```text
automatic.en.txt
    → segmentação em sentenças
    → lotes de 3 sentenças
    → <s> sentença </s>
    → Gemma-APS
    → grupos de proposições
    → automatic.en.claims.json
```

## 13. Resultado quantitativo

```text
Modelo: google/gemma-2b-aps-it
Sentenças: 19
Chunks: 7
Claims: 52
Inferência: 41,765 segundos
Pico de VRAM: 4,696 GiB
```

Médias derivadas:

- 2,74 claims por sentença;
- 5,97 segundos por chunk;
- aproximadamente 1,25 claims por segundo.

O teste demonstra que o modelo cabe com folga na RTX 2080 de 8 GB e pode processar o transcript sem quantização.

## 14. Avaliação qualitativa inicial

| Critério | Avaliação inicial |
|---|---|
| Atomicidade | Alta |
| Cobertura | Alta |
| Fidelidade | Boa, mas com erros importantes |
| Decontextualização | Baixa/moderada |
| Fluência | Geralmente boa |
| Redundância | Moderada |
| Detecção de claims verificáveis | Não realizada |

### 14.1 Pontos positivos

- Boa decomposição de conjunções e enumerações.
- Separação de efeitos adversos em claims individuais.
- Preservação geral do conteúdo da passagem.
- Boa decomposição da última sentença em objetivos distintos: ajudar quem precisa, não focar estética, restaurar saúde e restaurar qualidade de vida.

### 14.2 Problemas encontrados

#### Perguntas e títulos tratados como claims

```text
Weight-loss pens.
Have you ever used one?
Do you know someone who has used one?
```

Isso mostra que APS não substitui Claim Span Identification ou check-worthiness filtering.

#### Fragmentos sem sujeito

```text
sold under the brand name Saxenda.
known as Wegovy.
known as Ozempic.
sold as Mounjaro.
```

Esses itens não são autocontidos e falham em decontextualização.

#### Referências contextuais não resolvidas

Exemplos: `these medications`, `these people`, `it`, `the medication`, `the treatment`, `that` e `your case`.

#### Alterações de significado

Origem:

```text
Obesity is a chronic disease, like diabetes or hypertension.
```

Saída problemática:

```text
Obesity is like diabetes.
Obesity is like hypertension.
```

A comparação específica entre doenças crônicas foi generalizada.

Outro caso:

```text
These medications are sold only with a prescription to protect your health.
```

Gerou:

```text
These medications are sold to protect your health.
```

O vínculo entre proteção e exigência de receita foi perdido.

#### Redundância

```text
Improper use can cause adverse effects.
Improper use without medical guidance can cause adverse effects.
```

O segundo claim já contém o primeiro.

#### Perda de informação

O modelo extraiu a perda excessiva de massa muscular, mas omitiu a proposição de que essa perda é chamada de sarcopenia.

## 15. Conclusão metodológica

O Gemma-APS foi validado tecnicamente no hardware disponível e é um baseline forte para:

```text
Atomic Claim Decomposition
```

Ele não executa satisfatoriamente, sozinho:

```text
Claim Span Identification
Claim Normalization
Full Decontextualization
Fact Verification
```

Sua posição mais adequada na pipeline é:

```text
Transcript
    ↓
Claim Span Identification
    ↓
Gemma-APS: Atomic Claim Decomposition
    ↓
Claim Normalization
    ↓
Decontextualization
    ↓
Final claims
```

O modelo continua sendo candidato ao **Modelo A**, mas deve ser descrito como baseline científico de APS/atomicidade, e não como sistema end-to-end completo de Claim Extraction.

## 16. Próximos passos recomendados

1. Congelar os inputs traduzidos e registrar a política de tradução/limpeza de ASR.
2. Criar um pequeno golden set humano com claims atômicos e autocontidos.
3. Executar o Gemma-APS nos mesmos held-out transcripts usados por B e C.
4. Medir Atomicity, Faithfulness, Decontextualization, Fluency, Focus, Coverage, `F_fact` e Redundancy.
5. Aplicar métricas de Claimify e FEVERFact/FENICE conforme a metodologia final.
6. Registrar erros de questions-as-claims, fragmentos, referências não resolvidas, redundância e perda de conteúdo.
7. Testar o Modelo B comunitário com exatamente os mesmos inputs.
8. Definir se o Modelo C será um modelo end-to-end ou uma composição modular com CSI, APS, normalização e decontextualização.

## 17. Comandos úteis

Sincronizar o ambiente:

```bash
uv sync
```

Validar o script:

```bash
uv run python -m py_compile src/inference.py
uv run python src/inference.py --help
```

Visualizar o JSON:

```bash
uv run python -m json.tool output/automatic.en.claims.json | less
```

Verificar GPU:

```bash
nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free --format=csv
```

Verificar identidade no Hugging Face:

```bash
uv run hf auth whoami
```
