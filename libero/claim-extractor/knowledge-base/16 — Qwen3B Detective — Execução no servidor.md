# Claim Extractor — Resumo do smoke test no servidor cuba

Data do resumo: 11/10/2026. Diagnósticos registrados na conversa: 10/10/2026.

## 1. Objetivo e restrições

Executar um primeiro smoke test do modelo comunitário **Luimas/claim-extractor-detective-qwen3b**, candidato ao Modelo B do projeto de doutorado sobre extração de claims de transcrições de vídeos sobre GLP-1.

O usuário quer seguir as instruções do repositório, usando `uv` para gerenciar o ambiente. A configuração deve avançar em etapas pequenas, começando por um único modelo e uma única inferência. A CPU e a GPU do servidor não podem ser substituídas.

**Estado atual: nenhuma inferência bem-sucedida foi registrada.** O caminho GGUF está bloqueado por `Illegal instruction` durante a consulta de suporte a GPU. Foi identificado um caminho alternativo com Transformers, documentado pelo próprio autor, mas ainda não testado.

## 2. Ambiente confirmado

| Item | Valor observado |
|---|---|
| Servidor / usuário | `libero_neto@cuba` |
| Diretório real do projeto | `/home/libero_neto/claim_extractor/claim-extractor-detective-qwen3b` |
| CPU | Intel Xeon E5620 @ 2.40 GHz |
| Instruções da CPU | SSE4.1 e SSE4.2; sem AVX, AVX2, FMA ou F16C nas flags apresentadas |
| GPU | NVIDIA GeForce RTX 2080 |
| VRAM detectada | 7967 MiB |
| Compute capability | 7.5 |
| Python | 3.10.12 |
| Ambiente virtual | `.venv` dentro do diretório do modelo |
| Gerenciador de pacotes | `uv` |
| Ferramentas de compilação | `gcc`, `g++`, `cmake` e `make` disponíveis em `/usr/bin` |
| Compilador CUDA `nvcc` | Não encontrado no PATH; o pacote Python instalado também não forneceu o executável procurado |
| Debugger `gdb` | Não instalado |
| Log do kernel | Leitura de `dmesg` bloqueada para a conta |

A GPU deste servidor é a RTX 2080. Não confundir com a RTX 2060 SUPER da máquina pessoal mencionada em outras conversas.

## 3. Organização mínima proposta

Foi proposta a seguinte organização dentro do diretório do modelo:

| Pasta | Finalidade |
|---|---|
| `repository/` | Modelo, prompt, gramática e scripts oficiais |
| `input/` | Texto usado no smoke test |
| `output/` | JSON, logs e diagnósticos |
| `cache/uv/` | Cache do gerenciador de pacotes |
| `cache/huggingface/` | Cache dos downloads |
| `.venv/` | Ambiente Python do modelo |

O caminho real foi confirmado pelo terminal. A conversa não inclui uma listagem completa que confirme todas essas pastas e todos os artefatos. Os caminhos anteriores `claim-extractor-test` e `claim-extractor-model-b` não devem substituir o caminho real acima.

## 4. Modelo e caminhos documentados

Repositório: [Luimas/claim-extractor-detective-qwen3b](https://huggingface.co/Luimas/claim-extractor-detective-qwen3b).

Segundo o model card consultado na conversa, o extrator usa Qwen2.5-3B, foi ajustado com QLoRA e destilação de um Qwen2.5-14B, e trabalha com textos em inglês. Produz claims e metadados para verificação; não atribui um veredito de verdade às afirmações.

O autor documenta dois caminhos de inferência:

| Caminho | Artefatos e script | Características |
|---|---|---|
| GGUF / llama.cpp | `Qwen2.5-3B-Instruct.Q4_K_M.gguf`, `prompt.txt`, `claim.gbnf`, `scripts/inference.py` | Modelo quantizado; decodificação restringida pela gramática GBNF |
| Hugging Face / Transformers | Pesos HF em `*.safetensors`, configuração, tokenizer e `scripts/inference_hf.py` | O model card descreve um modelo merged FP16 e fornece um comando específico para esse caminho |

Comando de exemplo documentado para Transformers:

```bash
python scripts/inference_hf.py --text "Paste any English paragraph."
```

Esse comando é uma referência do autor, não uma execução já validada no servidor. O arquivo `inference_hf.py` ainda precisa ser inspecionado para confirmar dependências, seleção de dispositivo, dtype, limites de geração e tratamento do JSON.

O model card também informa truncamento de entrada para aproximadamente 4000 caracteres. O teste de uma transcrição longa precisará considerar esse limite; divisão em blocos e deduplicação permanecem fora do primeiro smoke test.

## 5. Pacotes instalados e verificação Python

Últimas versões confirmadas pelo terminal:

| Pacote | Versão |
|---|---|
| `llama-cpp-python` | 0.3.36 |
| `nvidia-cuda-runtime-cu12` | 12.4.127 |
| `nvidia-cublas-cu12` | 12.4.5.8 |
| `nvidia-cuda-nvcc-cu12` | 12.4.131 |

Antes do ajuste, estavam instalados runtime CUDA 12.9.79 e cuBLAS 12.9.2.10. Foram substituídos pelas versões 12.4 para alinhar o ambiente ao caminho CUDA 12.4 escolhido. A troca não resolveu o `Illegal instruction`.

`uv pip check --python .venv/bin/python` informou que os 22 pacotes então instalados eram compatíveis. Isso verifica dependências Python, mas não garante que bibliotecas nativas estejam localizáveis nem que os binários sejam compatíveis com as instruções da CPU.

## 6. Histórico dos diagnósticos

### 6.1. Biblioteca CUDA ausente

O primeiro `import llama_cpp` falhou ao carregar `libllama.so`:

```text
libcudart.so.12: cannot open shared object file: No such file or directory
```

Foram instalados runtime CUDA e cuBLAS na `.venv`, e seus diretórios foram acrescentados ao `LD_LIBRARY_PATH`:

```bash
cd /home/libero_neto/claim_extractor/claim-extractor-detective-qwen3b

PYTHON_SITE="$PWD/.venv/lib/python3.10/site-packages"

export LD_LIBRARY_PATH="$PYTHON_SITE/nvidia/cuda_runtime/lib:$PYTHON_SITE/nvidia/cublas/lib:${LD_LIBRARY_PATH:-}"
```

Depois desse ajuste, `ldd` não mostrou bibliotecas ausentes no diagnóstico apresentado.

### 6.2. Falha com instrução inválida

A biblioteca passou a importar. Ao chamar `llama_supports_gpu_offload()`, o backend detectou a RTX 2080 e depois o processo encerrou:

```text
llama-cpp-python: 0.3.36
ggml_cuda_init: found 1 CUDA devices (Total VRAM: 7967 MiB):
  Device 0: NVIDIA GeForce RTX 2080, compute capability 7.5, VMM: yes, VRAM: 7967 MiB
Illegal instruction
```

O mesmo erro persistiu depois de fixar runtime e cuBLAS em CUDA 12.4.

As saídas de `lscpu` e `/proc/cpuinfo` confirmaram ausência de AVX, AVX2, FMA e F16C. Isso torna uma instrução incompatível em código nativo uma hipótese forte, mas **a biblioteca e a instrução exatas ainda não foram identificadas**.

### 6.3. Teste com GPU ocultada

O teste com `CUDA_VISIBLE_DEVICES=""` também terminou com `Illegal instruction`, após a mensagem de que nenhum dispositivo CUDA estava disponível.

Esse teste mostra que ocultar a GPU não elimina a falha. Não prova isoladamente que ela esteja em `libggml-cpu`, pois a build CUDA e suas bibliotecas continuaram carregadas.

### 6.4. Limitações de depuração

- `gdb` retornou `command not found`.
- `output/sigill-gdb.txt` contém apenas esse erro, não um stack trace.
- `dmesg` retornou `Operation not permitted`.

### 6.5. Pacote de componentes CUDA sem `nvcc`

Foi instalado `nvidia-cuda-nvcc-cu12==12.4.131`. A sugestão de que ele forneceria `nvidia/cuda_nvcc/bin/nvcc` estava incorreta para o pacote observado.

A busca encontrou somente:

```text
.venv/lib/python3.10/site-packages/nvidia/cuda_nvcc/bin/ptxas
```

O executável `nvcc` necessário à compilação não foi encontrado nessa instalação.

## 7. Correções de interpretação

1. `Illegal instruction` não identifica automaticamente AVX como causa exata. A CPU não tem AVX, mas ainda falta localizar a instrução que provocou o SIGILL.
2. A versão CUDA exibida pelo driver não comprova instalação do Toolkit nem presença de `nvcc`. Também não deve ser tratada, isoladamente, como prova de incompatibilidade de todas as bibliotecas de versões menores posteriores; existe compatibilidade entre versões menores em determinadas condições.
3. O pacote Python `nvidia-cuda-nvcc-cu12` instalado não substituiu o Toolkit necessário para a compilação proposta.
4. A instalação local do Toolkit foi sugerida antes de explorar o caminho Transformers já documentado pelo autor.
5. A conversa não confirma download ou instalação do Toolkit completo, compilação própria, download dos pesos do modelo ou execução do smoke test.

## 8. Caminho proposto para continuar

A última recomendação foi avaliar o caminho oficial **Transformers + `inference_hf.py`**, usando a mesma CPU e a mesma GPU.

Essa rota evita compilar `llama-cpp-python` e, com pacotes PyTorch CUDA pré-compilados compatíveis, não exige `nvcc` para a inferência. Ainda precisa de validação no servidor:

1. Inspecionar `scripts/inference_hf.py` e `requirements.txt` antes de escolher os pacotes.
2. Testar importação e uma operação CUDA pequena com PyTorch nesse Xeon sem AVX.
3. Confirmar VRAM livre e carregamento em FP16 apropriado à RTX 2080. Os pesos de um modelo com aproximadamente 3B parâmetros em 16 bits ocupam cerca de 6 GB, antes de cache e buffers; esse é um cálculo aproximado, não uma medição no servidor.
4. Baixar os pesos e artefatos HF necessários apenas após validar o runtime.
5. Executar um texto curto em inglês e registrar saída, erros, tempo e uso de GPU.
6. Verificar o JSON produzido. A garantia de JSON válido atribuída à gramática GBNF do caminho GGUF não deve ser automaticamente estendida ao caminho Transformers sem inspeção do script.

Se Transformers também não funcionar, permanece possível estudar uma build de llama.cpp/llama-cpp-python compatível com SSE4.2 e CUDA. As flags de CPU, arquitetura CUDA 75 e opções de compilação deverão ser verificadas na versão escolhida. Essa alternativa não foi executada nem comprovada nesta conversa.

## 9. Referências

- [Model card e instruções do autor](https://huggingface.co/Luimas/claim-extractor-detective-qwen3b)
- [Arquivos do repositório](https://huggingface.co/Luimas/claim-extractor-detective-qwen3b/tree/main)
- [Documentação do uv](https://docs.astral.sh/uv/)
- [llama-cpp-python](https://github.com/abetlen/llama-cpp-python)
- [Guia NVIDIA de instalação do CUDA 12.4 no Linux](https://docs.nvidia.com/cuda/archive/12.4.0/cuda-installation-guide-linux/)

## 10. Ponto de retomada

Continuar pelo diretório real `/home/libero_neto/claim_extractor/claim-extractor-detective-qwen3b`. O próximo passo é inspecionar e validar o caminho Transformers do autor, sem presumir que PyTorch funcionará nesse Xeon ou que o modelo caberá com folga nos 8 GB de VRAM. O usuário prefere um passo por vez e não pode trocar a CPU nem a GPU.
