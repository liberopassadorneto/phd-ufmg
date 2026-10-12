# Claim Extractor — sequential benchmark on cuba

The runner attempts all 12 distinct model checkpoints listed in
**knowledge-base/all_models.md**. It runs one model at a time on the GPU, saves
inputs, raw outputs and metrics, stops the worker process, and removes temporary
weights before starting the next checkpoint. The GitHub pipelines listed in that
document are references for model usage; they are not additional benchmark entries.

## Running on the server

Copy this project, including **claim_runner/**, **runtimes/** and the three input
files, to a directory on cuba. Run the script inside your SSH session.

From the copied project directory:

~~~bash
uv sync --frozen
uv run --frozen hf auth login
uv run --frozen run_models.py --list-models

# Install the classic runtime and check a CUDA operation without downloading models.
uv run --frozen run_models.py --check --models gemma-2b-aps

# Run the first baseline before trying larger models.
uv run --frozen run_models.py --models gemma-2b-aps

# Check NF4 quantization on CUDA before downloading a larger model.
uv run --frozen run_models.py --check --models dongyru-mistral
uv run --frozen run_models.py --models dongyru-mistral

# Select one checkpoint, several checkpoints, or all 12 checkpoints.
uv run --frozen run_models.py --models gemma-2b-aps,detective-qwen3b
uv run --frozen run_models.py --models all --output-dir results
~~~

Accept the licenses for [Gemma](https://huggingface.co/google/gemma-2b-aps-it)
and the [Llama base used by NewsScope](https://huggingface.co/meta-llama/Meta-Llama-3.1-8B-Instruct)
using the account associated with your token. An HTTP response from the website
does not confirm access to gated weights. The token remains in the normal Hugging
Face configuration and is not copied to the results.

Each run gets a unique directory with a UTC timestamp and an identifier. The runner
continues after individual model failures. Exit code 1 indicates an incomplete
sequence; 130 indicates interruption. A cleanup failure stops the sequence to
prevent checkpoints from accumulating. For long runs, use an existing tmux session
or another persistent session available on the server.

## Hardware and storage configuration

The defaults target cuba: Python 3.10, torch 2.6.0/CUDA 12.4, eight physical CPU
cores, an RTX 2080/Turing GPU, and one inference operation at a time. The supervisor
and the classic and modern runtimes have separate dependency lockfiles. The modern
runtime uses Transformers 5.5.0 and Orbitals 0.6.1; the classic runtime uses
Transformers 4.57.6 and PEFT 0.18.0.

- Gemma-2B, Detective and Principled-2B: FP16 on CUDA.
- T5 and ClaimPT: FP32 on CUDA.
- Gemma-7B, Principled-4B, NewsScope and Mistral models: NF4 with FP16 computation.
- If NF4 fails or VRAM is insufficient, a second attempt can keep FP16 weights in
  RAM and transfer modules to CUDA for execution through Accelerate. This avoids
  computing those modules on the Xeon, but increases transfers and may be much slower.

The runner uses native PyTorch kernels: SDPA where supported, with Flash SDPA
disabled, and eager attention otherwise. The PyTorch path for Qwen3.5 may be slower
than the author's optimized implementations. Principled checkpoints are loaded
using the native multimodal class with text-only input; vision weights are included
in the memory budget.

The supervisor checks FP16 and NF4 in isolated processes. A SIGILL during a probe
does not crash the sequence. These dependency versions are candidates for this
hardware: dependency resolution and CPU tests do not establish successful inference
on the Xeon without AVX.

Before downloading each checkpoint, the runner queries file sizes and pins its SHA
revision. It downloads one representation of the weights, excluding GGUF, training
data and duplicate weights. Quantization during loading does not reduce download size.

The default temporary directory is **.model-staging/**. If disk space is insufficient,
the runner tries the existing tmpfs at **/dev/shm**, accounting for both staged files
and the RAM needed to load the model. Reserved resources are 5 GiB of disk space,
8 GiB of RAM and 1 GiB of VRAM.

The published SAGESSE weights occupy approximately 27 GiB (29 decimal GB), before
buffers and metadata. With the reported 27 GB of free disk space, that checkpoint
requires staging in RAM or another filesystem with sufficient capacity.

~~~bash
# Inspect available resources before running the complete sequence.
df -h / /dev/shm
free -h

# Use an existing larger mounted volume, if available.
uv run --frozen run_models.py --models all --staging-dir /path/to/volume/staging

# Adjust resource budgets and configuration.
uv run --frozen run_models.py --models gemma-7b-aps \
  --gpu-reserve-gib 1 --ram-reserve-gib 8 --disk-reserve-gib 5 \
  --cpu-threads 8 --context-tokens 8192

# Explicitly choose execution with weights stored in RAM.
uv run --frozen run_models.py --models sagesse-mistral --precision offload
~~~

The uv environments and package cache remain installed and consume disk space.
The runner checks available space again after installation. The Xet download cache
is disabled. Cleanup removes only temporary directories with a valid ownership
marker; outputs, inputs, environments and pre-existing user caches are preserved.

SIGINT and SIGTERM stop the subprocess and clean up staging. SIGKILL, power loss or
filesystem loss may leave a temporary directory. In those cases, inspect the path
recorded in result.json before manually removing that directory.

## Input and output protocols

| Alias | Checkpoint / protocol |
|---|---|
| gemma-2b-aps | [google/gemma-2b-aps-it](https://huggingface.co/google/gemma-2b-aps-it); APS sentence markers and chat template. |
| gemma-7b-aps | [google/gemma-7b-aps-it](https://huggingface.co/google/gemma-7b-aps-it); the same APS protocol. |
| detective-qwen3b | [Luimas](https://huggingface.co/Luimas/claim-extractor-detective-qwen3b); official prompt.txt, at most 4,000 characters per chunk. |
| newsscope | [nidhipandya/NewsScope-lora](https://huggingface.co/nidhipandya/NewsScope-lora); Llama 3.1 8B base plus PEFT, text prompt from [GitHub](https://github.com/nidhip1611/NewsScope), sampling with temperature 0.3 and seed 42. |
| babelscape-t5 | [Babelscape T5](https://huggingface.co/Babelscape/t5-base-summarization-claim-extractor); direct text input and string output. |
| claimpt | [lfcc/bert-claimpt-chunk](https://huggingface.co/lfcc/bert-claimpt-chunk); Portuguese token classification, 512-token windows and 128-token overlap. |
| principled-4b | [Principled 4B](https://huggingface.co/principled-intelligence/claim-extractor-4B-q-2605); official [Orbitals](https://github.com/Principled-Intelligence/orbitals) preparation. |
| principled-2b | [Principled 2B](https://huggingface.co/principled-intelligence/claim-extractor-2B-q-2605); the same preparation. |
| dongyru-mistral | [dongyru/Mistral-7B-Claim-Extractor](https://huggingface.co/dongyru/Mistral-7B-Claim-Extractor); empty model card, benchmark-authored prompt identified in the catalog. |
| fc-claim-det-t5 | [FC-Claim-Det T5](https://huggingface.co/varadhbhatnagar/fc-claim-det-T5-base); removes mentions/hashtags, normalizes/summarizes; six beams, ngram size 2, minimum length 5 and at most 15 new tokens. |
| sagesse-mistral | [SAGESSE](https://huggingface.co/SAGESSE-EPFL/Mistral-7b-claims-extraction); template extracted from the pinned README, with empty context fields. |
| mistral-instruct-v02 | [Mistral-7B-Instruct-v0.2](https://huggingface.co/mistralai/Mistral-7B-Instruct-v0.2); benchmark-authored prompt; this is not a FEVERFact fine-tuned checkpoint. |

Confirmed smaller variants are Gemma-2B-APS for the Gemma-APS family and
Principled-2B for Principled. Searches of the authors' catalogs did not find smaller
variants of the same NewsScope, dongyru or SAGESSE extractor. Selecting a larger
checkpoint always attempts that checkpoint.

The generators use the frozen translation in **automatic.en.txt**. ClaimPT receives
**automatic.srt**, with caption indices and timestamps removed. Differences in
language and task are recorded in the metadata; results do not automatically form
a performance ranking.

Gemma uses **automatic.en.aps-input.jsonl**, validated against the translation's
19 sentences: seven chunks of at most three sentences. Custom English input can
have its own APS JSONL. Without that file, the supervisor segments the custom text
with NLTK and creates chunks of three sentences. The runner does not translate or
perform additional ASR corrections.

~~~bash
uv run --frozen run_models.py --models gemma-2b-aps \
  --input-en /path/to/transcript.en.txt --aps-input /path/to/prompts.aps.jsonl

uv run --frozen run_models.py --models detective-qwen3b,newsscope \
  --input-en /path/to/transcript.en.txt
~~~

Other generators receive the entire text when it fits. Splitting accounts for the
rendered prompt, output budget, checkpoint context and the author's specific input
limit. The default overall context ceiling is 8192 tokens. Splitting preserves all
source text; intentional FC-T5 preprocessing is recorded separately.

Default output limits are APS 512, Detective 768, NewsScope 2000, Babelscape 512,
Principled 4096, Mistral 2048 and FC-T5 15. These budgets, greedy decoding outside
NewsScope, and NF4 are benchmark configurations recorded as protocol adaptations.
The Orbitals prompt disables thinking and does not invent a service description.
Raw extractions are preserved before parsing.

A chunk that reaches its generation limit without EOS makes the result partial.
Adjust **--max-new-tokens** and **--context-tokens** when needed. Inputs are never
silently truncated. Invalid JSON produces a separate parsing error and does not
erase the generation. Valid JSON with empty claims remains distinct from a parsing error.

## Artifacts and metrics

Each run directory contains:

~~~text
run.json
summary.json
summary.csv
preflight/<runtime>/...
<model>/
  model-card.json
  input.json
  download-manifest.json
  upstream-*/README.md, available configs, prompts and schemas
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
  attempt-2-offload/...       when needed
~~~

ClaimPT also saves each window in a **.logits.npz** file containing logits, input IDs
and offsets. raw.jsonl references those files and records labels. Overlapping
windows remain separate; spans are not presented as normalized generative claims.

Text outputs include generated token IDs and decoding both with and without special
tokens. Deduplication, fact verification and JSON repair never modify raw.jsonl.
The job.json files record temporary paths that no longer exist after cleanup;
hashes, revisions and inputs remain available.

Preflight, download, loading, inference, cleanup and total times are reported
separately. CUDA execution is synchronized before and after each generation.
Resources are sampled once per second:

- Subprocess and child-process RAM/RSS and CPU; CPU can exceed 100% across multiple cores.
- System available/used RAM, swap and CPU.
- Process VRAM, device VRAM and device utilization through NVML.
- PyTorch peak allocated/reserved memory, including loading.
- Staging size and filesystem free space; tmpfs RAM contributes to system memory usage.

Sampling may miss peaks shorter than one second. Device VRAM includes other
processes; RSS does not account for all files stored in tmpfs. Unavailable metrics
are null or accompanied by a reason. worker-result.json complements sampling with
Linux maximum RSS and CPU time for the worker itself. Storage and memory values
are reported in bytes; one GiB is 1024³ bytes.

When a retry occurs, the summary aggregates attempt times while preserving each
attempt's configuration and outputs. Compare the selected attempt when studying
precision versus offload; total sequence time includes preparation and failed attempts.

## Validation

~~~bash
uv run --frozen python -m unittest discover -s tests -v
~~~

Tests use CPU, local inputs and mocked failures to check the seven frozen chunks,
lossless splitting, selection of all 12 checkpoints, restricted cleanup, tmpfs
budgeting, interrupted downloads and a fresh attempt after OOM.

Before benchmarking on cuba, run the checks and the two individual model executions
shown at the beginning. Resolving lockfiles and testing the supervisor do not
replace validation of model loading, output quality and performance on the RTX 2080
and Xeon.
