# Claim Extractor — benchmark sequencial no cuba

O runner executa os 12 checkpoints distintos de **knowledge-base/all_models.md**.
Ele usa uma GPU por vez, salva entradas, saídas brutas e métricas, encerra o processo
e remove os pesos temporários antes de iniciar o próximo checkpoint.

## Execução no servidor

Copie este projeto, incluindo **claim_runner/**, **runtimes/** e os três inputs,
para uma pasta no cuba. O script roda dentro da sessão SSH; ele não configura
o daemon SSH nem precisa de acesso root.

Na pasta copiada:

~~~bash
uv sync --frozen
uv run --frozen hf auth login
uv run --frozen run_models.py --list-models

# Instala o runtime clássico e testa uma operação CUDA; não baixa modelos.
uv run --frozen run_models.py --check --models gemma-2b-aps

# Primeiro baseline, antes dos modelos grandes.
uv run --frozen run_models.py --models gemma-2b-aps

# Testa quantização NF4 em CUDA antes de baixar um modelo grande.
uv run --frozen run_models.py --check --models dongyru-mistral
uv run --frozen run_models.py --models dongyru-mistral

# Um, vários ou todos os checkpoints.
uv run --frozen run_models.py --models gemma-2b-aps,detective-qwen3b
uv run --frozen run_models.py --models all --output-dir results
~~~

Aceite previamente as licenças de [Gemma](https://huggingface.co/google/gemma-2b-aps-it)
e da base [Llama usada pelo NewsScope](https://huggingface.co/meta-llama/Meta-Llama-3.1-8B-Instruct)
na conta vinculada ao token. O login HTTP do site não comprova acesso aos pesos.
O token fica na configuração normal do Hugging Face e não é copiado aos resultados.

Cada execução recebe uma pasta exclusiva, com timestamp UTC e identificador.
O runner continua após erros individuais; código de saída 1 significa sequência
incompleta e 130 significa interrupção. Falha na limpeza encerra a sequência para
impedir o acúmulo de checkpoints. Para processos longos, execute dentro de uma
sessão tmux existente ou outra sessão persistente disponível no servidor.

## Configuração de hardware e armazenamento

Defaults direcionados ao cuba: Python 3.10, torch 2.6.0/CUDA 12.4, CPU com oito
cores físicos, RTX 2080/Turing e uma operação de inferência por vez. As dependências
do supervisor e dos runtimes clássico/moderno possuem lockfiles próprios. O
runtime moderno usa Transformers 5.5.0 e Orbitals 0.6.1; o clássico usa
Transformers 4.57.6 e PEFT 0.18.0.

- Gemma-2B, Detective e Principled-2B: FP16 em CUDA.
- T5 e ClaimPT: FP32 em CUDA.
- Gemma-7B, Principled-4B, NewsScope e os modelos Mistral: NF4 com cálculo FP16.
- Em falha de NF4 ou falta de VRAM, uma segunda tentativa pode manter pesos FP16
  em RAM e transferir os módulos para execução CUDA usando Accelerate. Essa
  alternativa evita computar os módulos no Xeon, mas aumenta transferências e
  pode ser muito mais lenta.

São usados kernels nativos do PyTorch: SDPA quando o modelo oferece suporte,
com Flash SDPA desativado, e atenção eager nos outros casos. Não são instalados
llama.cpp, FlashAttention, Unsloth ou kernels opcionais de Qwen. O caminho PyTorch
de Qwen3.5 pode ser mais lento que as implementações otimizadas do autor.
Os checkpoints Principled são carregados pela classe multimodal nativa, com
entrada exclusivamente textual; os pesos visuais também constam no orçamento.

O supervisor testa FP16 e NF4 em processos isolados. Um SIGILL no probe não
derruba a sequência. As versões são candidatas para este hardware: resolver
dependências e passar os testes de CPU não comprova inferência no Xeon sem AVX.

Antes de baixar cada checkpoint, o runner consulta tamanhos e fixa revisões SHA.
Ele baixa uma única representação dos pesos, excluindo GGUF, dados de treino e
pesos duplicados. Quantizar durante o carregamento não reduz o tamanho do download.

Por padrão, a pasta temporária fica em **.model-staging/**. Se faltar espaço,
o runner tenta o tmpfs existente em **/dev/shm**, considerando conjuntamente
o tamanho dos arquivos e a RAM necessária para carregar o modelo. Não cria ou
redimensiona mounts. Reservas: 5 GiB de disco, 8 GiB de RAM e 1 GiB de VRAM.

Os pesos publicados do SAGESSE ocupam aproximadamente 27 GiB (29 GB decimais),
antes de buffers e metadados. Com os 27 GB livres informados, esse checkpoint
precisa de staging em RAM ou de outro filesystem com capacidade suficiente.

~~~bash
# Inspecionar espaço real antes de uma sequência completa.
df -h / /dev/shm
free -h

# Usar um volume maior já montado, se disponível.
uv run --frozen run_models.py --models all --staging-dir /caminho/do/volume/staging

# Controlar orçamento e configuração.
uv run --frozen run_models.py --models gemma-7b-aps \
  --gpu-reserve-gib 1 --ram-reserve-gib 8 --disk-reserve-gib 5 \
  --cpu-threads 8 --context-tokens 8192

# Optar explicitamente pela execução com pesos em RAM.
uv run --frozen run_models.py --models sagesse-mistral --precision offload
~~~

Os ambientes uv e seu cache de pacotes permanecem instalados e também consomem
disco. O runner reavalia o espaço depois da instalação; esses arquivos não são
pesos de modelos. O cache Xet de downloads é desativado. Apenas diretórios
temporários com marcador de propriedade válido são removidos. Outputs, inputs,
ambientes e caches anteriores do usuário são preservados.

SIGINT e SIGTERM param o subprocesso e limpam o staging. SIGKILL, queda de energia
ou perda do filesystem podem deixar uma pasta temporária; nesses casos, examine
o caminho registrado no result.json antes de remover manualmente a pasta.

## Protocolos de entrada e saída

| Alias | Checkpoint / protocolo |
|---|---|
| gemma-2b-aps | [google/gemma-2b-aps-it](https://huggingface.co/google/gemma-2b-aps-it); APS com marcadores e chat template. |
| gemma-7b-aps | [google/gemma-7b-aps-it](https://huggingface.co/google/gemma-7b-aps-it); mesmo protocolo APS. |
| detective-qwen3b | [Luimas](https://huggingface.co/Luimas/claim-extractor-detective-qwen3b); prompt.txt oficial, até 4.000 caracteres por chunk. |
| newsscope | [nidhipandya/NewsScope-lora](https://huggingface.co/nidhipandya/NewsScope-lora); base Llama 3.1 8B + PEFT, prompt textual do [GitHub](https://github.com/nidhip1611/NewsScope), geração com sampling, temperatura 0.3 e seed 42. |
| babelscape-t5 | [Babelscape T5](https://huggingface.co/Babelscape/t5-base-summarization-claim-extractor); texto direto, saída em string. |
| claimpt | [lfcc/bert-claimpt-chunk](https://huggingface.co/lfcc/bert-claimpt-chunk); token classification em português, janelas 512 e overlap 128. |
| principled-4b | [Principled 4B](https://huggingface.co/principled-intelligence/claim-extractor-4B-q-2605); preparação oficial do [Orbitals](https://github.com/Principled-Intelligence/orbitals). |
| principled-2b | [Principled 2B](https://huggingface.co/principled-intelligence/claim-extractor-2B-q-2605); mesma preparação. |
| dongyru-mistral | [dongyru/Mistral-7B-Claim-Extractor](https://huggingface.co/dongyru/Mistral-7B-Claim-Extractor); card vazio, prompt próprio do benchmark identificado no catálogo. |
| fc-claim-det-t5 | [FC-Claim-Det T5](https://huggingface.co/varadhbhatnagar/fc-claim-det-T5-base); remove mentions/hashtags, normaliza/sumariza; seis beams, ngram 2, comprimento mínimo 5 e até 15 novos tokens. |
| sagesse-mistral | [SAGESSE](https://huggingface.co/SAGESSE-EPFL/Mistral-7b-claims-extraction); template extraído do README fixado, campos de contexto vazios. |
| mistral-instruct-v02 | [Mistral-7B-Instruct-v0.2](https://huggingface.co/mistralai/Mistral-7B-Instruct-v0.2); prompt próprio; não representa um checkpoint FEVERFact fine-tuned. |

Variantes menores confirmadas: Gemma-2B-APS para a família Gemma-APS e
Principled-2B para Principled. Nas consultas aos catálogos dos autores, não foram
encontradas variantes menores do mesmo extrator NewsScope, dongyru ou SAGESSE.
Selecionar o modelo grande não o substitui silenciosamente pelo menor.

A tradução **automatic.en.txt** é usada nos geradores. ClaimPT recebe
**automatic.srt**, removendo apenas índices e timestamps. As diferenças de tarefa
e idioma ficam nos metadados; os resultados não formam um ranking automático.

Gemma usa **automatic.en.aps-input.jsonl**, validado contra as 19 sentenças da
tradução: sete blocos de até três sentenças. Input inglês customizado pode receber
um APS JSONL próprio; sem esse arquivo, o supervisor segmenta com NLTK e gera
blocos de três sentenças. Não realiza tradução ou correções adicionais de ASR.

~~~bash
uv run --frozen run_models.py --models gemma-2b-aps \
  --input-en /caminho/transcript.en.txt --aps-input /caminho/prompts.aps.jsonl

uv run --frozen run_models.py --models detective-qwen3b,newsscope \
  --input-en /caminho/transcript.en.txt
~~~

Os demais geradores recebem o texto inteiro quando couber. A divisão considera
o prompt renderizado, orçamento de output, contexto do checkpoint e limite
específico do autor. O teto geral default é 8192 tokens. Todo o texto é preservado
nas divisões; o pré-processamento intencional de FC-T5 é registrado separadamente.

Limites default de output: APS 512, Detective 768, NewsScope 2000, Babelscape 512,
Principled 4096, Mistral 2048, FC-T5 15. As escolhas de orçamento, greedy decoding
fora NewsScope e NF4 são configurações do benchmark, registradas como adaptações
do protocolo. O prompt de Orbitals desativa thinking e não inventa uma descrição
de serviço. O runner preserva as extrações brutas antes de qualquer parser.

Um chunk que atinge o limite de geração sem EOS torna o resultado parcial. Ajuste
**--max-new-tokens** e **--context-tokens** quando necessário; inputs nunca são
truncados silenciosamente. JSON inválido gera um erro de parsing separado e não
apaga a geração. Saída JSON vazia válida permanece distinta de erro de parsing.

## Artefatos e métricas

Na pasta de cada execução:

~~~text
run.json
summary.json
summary.csv
preflight/<runtime>/...
<model>/
  model-card.json
  input.json
  download-manifest.json
  upstream-*/README.md, configs, prompts e schemas disponíveis
  download-resources.jsonl
  result.json
  attempt-1-<precision>/
    job.json
    configuration.json
    effective-inputs.jsonl
    raw.jsonl
    parsed.jsonl
    resource-samples.jsonl
    worker-result.json
    process-result.json
    process.log
  attempt-2-offload/...       quando necessário
~~~

ClaimPT também salva cada janela em um arquivo **.logits.npz**, contendo logits,
IDs de entrada e offsets. O raw.jsonl referencia esses arquivos e registra labels.
As janelas com overlap permanecem separadas; nenhum span é apresentado como um
claim generativo normalizado.

As saídas textuais incluem IDs dos tokens gerados, decoding com tokens especiais
e decoding sem esses tokens. Nenhuma deduplicação, verificação de veracidade ou
reparação de JSON modifica o raw.jsonl. Os job.json registram caminhos temporários
que deixam de existir após a limpeza; os hashes, revisões e inputs permanecem.

Tempo de preflight, download, carregamento, inferência, limpeza e total ficam
separados. Tempos CUDA são sincronizados antes e depois de cada geração.
As métricas de recursos são amostradas a cada segundo:

- RAM/RSS e CPU do subprocesso e seus filhos; CPU pode exceder 100% com vários cores.
- RAM disponível/usada, swap e CPU do sistema.
- VRAM do processo, VRAM e utilização do dispositivo via NVML.
- Picos de memória alocada/reservada no PyTorch, incluindo carregamento.
- Tamanho do staging e espaço livre do filesystem; RAM do tmpfs integra o uso do sistema.

Picos amostrados podem perder eventos inferiores a um segundo. VRAM do dispositivo
inclui outros processos; RSS não inclui todos os arquivos armazenados em tmpfs.
Dados não disponíveis ficam nulos ou acompanhados de motivo. worker-result.json
complementa a amostragem com máximo RSS e tempo CPU do próprio worker via Linux.
Valores em bytes são exatos na unidade; GiB usa 1024³ bytes.

Se ocorrer retry, o resumo agrega tempos das tentativas; cada configuração e saída
permanece separada. Compare a tentativa selecionada ao estudar precisão versus
offload; total de sequência inclui preparação e tentativas malsucedidas.

## Validação

~~~bash
uv run --frozen python -m unittest discover -s tests -v
~~~

Os testes usam CPU, inputs locais e mocks para falhas: integridade dos sete blocos,
divisão sem perda, seleção dos 12 checkpoints, limpeza restrita, orçamento de
tmpfs, download interrompido e nova tentativa após OOM.

Antes de um benchmark no cuba, execute os checks e as duas execuções individuais
indicadas no início. A resolução dos lockfiles e os testes do supervisor não
substituem a validação de carregamento, qualidade e performance dos modelos na
RTX 2080 e no Xeon.
