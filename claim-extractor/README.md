# Claim Extractor

## Local execution on Cuba

`--models all` excludes NewsScope on Cuba: its NF4 attempt exceeded the VRAM
budget and RAM offload was too slow. Explicit `--models newsscope` remains
available, with automatic RAM offload disabled.

Prepare persistent weights, model cards and locked dependencies, then run the
catalog sequentially without network access:

```bash
bash run-cuba.sh prepare --models all
bash run-cuba.sh run --models all
```

Storage defaults to `~/phd-models`; override with `MODEL_STORAGE`. Results use
a fresh timestamped directory under its `results/` folder. For one model, replace
`all` in both commands with its alias. Local runs use the existing EN/PT input
pair and the shared prompt for models requiring user instructions. Checkpoints
and dependencies remain stored after each run. `inputs.json` freezes the processed
transcripts; each model directory contains native `output.raw`/`output*.json`,
`processing.json`, and per-attempt logs. Individual resource samples are not saved.
`summary.json` is updated after each model with timings, average/peak VRAM/RAM, CPU
average/peak percentages, CPU seconds, configured threads, and average/peak
logical CPUs used (`vcpu_*_used`, CPU percentage divided by 100). Missing
measurements remain null. This command runs all prepared models sequentially,
continues after individual failures, and never overwrites previous runs:

```bash
bash run-cuba.sh run --models all
```

Checkpoints and dependencies remain stored after each run. `--checkpoints-only` preparation
retains the legacy checkpoint-only workflow for Greenwich.

## Greenwich SSHFS (experimental)

Prepare checkpoints on Greenwich (after `uv run hf auth login` for gated models):

```bash
cd ~/phd-ufmg/claim-extractor
uv run --frozen prepare-models.py --models babelscape-t5 --storage ~/phd-models
```

Use `--models all` to prepare the catalog. On Cuba, after mounting Greenwich,
pass `--offline --remote-storage ~/greenwich-models` to `run_models.py`.
Offline refers to checkpoints: uv may still need network access to install the
separate model environments. SHA-256 is checked during preparation only.
Normal execution resolves the prepared manifest without scanning weight files,
checking sizes or hashing. Weight validation is restricted to preparation.
`run` does not launch CUDA/NF4 probes, compare dependency stamps, or impose a
VRAM reserve. Libraries report loading/inference errors normally. Explicit
`bash run-cuba.sh check --models all` retains runtime and CUDA/NF4 diagnostics.
Metrics and logs are preserved. `--gpu-reserve-gib` is accepted for compatibility
but has no effect.

The optional `--remote-storage ~/greenwich-models` profile requires the exact
Greenwich SSHFS mount. It stores per-model environments, checkpoints, caches,
temporary files and results there. Checkpoints are reused by repository and
revision; do not delete them while a run is active. The Hugging Face login
remains in its existing location. The project source remains local.

Run `bash run-greenwich.sh` from Cuba to execute the catalog sequentially with
separate logs and a 7200-second timeout per attempt. Set
`MODEL_TIMEOUT_SECONDS` to change that limit. Babelscape uses a 512-token input
ceiling and both generic Mistral models use `prompts/shared-zero-shot-v2.md`.
The script continues after individual failures and returns nonzero if any fail.
It uses a new timestamped results directory on every invocation.

For a single model, set `UV_PROJECT_ENVIRONMENT` and `UV_CACHE_DIR` on the
mounted filesystem before running the root uv project, then pass
`--remote-storage ~/greenwich-models`. Do not unmount during a run. Reconnect
SSHFS using the server's existing mount procedure after a disconnect and verify
with `findmnt -T ~/greenwich-models` before retrying. Remote operation has not
yet been validated with real models; monitor local disk use during the pilot.

## Future work

- TODO: Prepare Qwen3.5-2B supervised fine-tuning with QLoRA once annotated
  transcript-to-claim training examples are available. Keep training and
  held-out evaluation transcripts separate.

Run the models sequentially on cuba. Each model has its own Python executor,
uv project and lockfile. Results contain native model responses and processing
measurements only.

## One executor per model

Each `runtimes/<alias>/` directory contains:

```text
run.py           Input/output paths, sources, prompt, model loading and generation
pyproject.toml   Dependencies for this model
uv.lock          Locked dependencies for this model
.venv/           Created by uv; excluded from Git
```

`DEFAULT_INPUT`, `DEFAULT_OUTPUT`, `INPUT_CONFIGURATION`, `HARDWARE` and
`GENERATION` are visible in each `run.py`. The registry reads these files; the
central worker does not choose model prompts or decoding parameters.
Model libraries are imported inside the executor functions so listing models
and reading configurations do not load Torch or model weights.
The original `gemma-2b-aps-inference.py` remains a historical experiment;
the current model entrypoints are the `run.py` files listed below.

Run these commands from the `claim-extractor` directory:

```bash
uv run --frozen --project runtimes/gemma-2b-aps \
  runtimes/gemma-2b-aps/run.py --input automatic.en.txt \
  --output-dir results/author-protocol

uv run --frozen --project runtimes/claimpt \
  runtimes/claimpt/run.py --input automatic.srt \
  --output-dir results/author-protocol
```

uv installs the selected project's dependencies automatically. Individual
executors use the Python version selected by the outer uv invocation. To select
Python 3.10, pass `--python 3.10` to `uv run` before the script path.
Shared uv cache files are reused across projects; keep the cache and runtimes on
the same filesystem for Linux hardlinks to avoid copying large CUDA packages.

## Sequential execution

The supervisor retains the existing model selection interface:

```bash
uv sync --frozen
uv run --frozen hf auth login
uv run --frozen run_models.py --list-models
uv run --frozen run_models.py --models gemma-2b-aps,detective-qwen3b \
  --output-dir results/author-protocol
uv run --frozen run_models.py --models all \
  --output-dir results/author-protocol-all
```

It starts the corresponding `run.py` in each model's environment, downloads
one checkpoint at a time, records resource use and removes temporary weights
before proceeding. Dependencies remain cached. `--check` installs and probes the
selected runtimes without downloading model weights or generating responses.
Accept the Gemma and Meta Llama access conditions on Hugging Face before
downloading gated checkpoints; NewsScope requires its Llama base.

## Published protocols and generation settings

These defaults follow the referenced author example or checkpoint configuration.
An example's token budget is not a mandatory architectural limit.

| Model executor | Default input and protocol | Generation | Output |
|---|---|---|---|
| [Gemma 2B](runtimes/gemma-2b-aps/run.py) | English; NLTK sentence markers and official chat template | 4,096 new tokens; deterministic | `.raw` |
| [Gemma 7B](runtimes/gemma-7b-aps/run.py) | Same published APS format | 4,096 new tokens; deterministic | `.raw` |
| [Detective Qwen3B](runtimes/detective-qwen3b/run.py) | English; published `prompt.txt` and Transformers chat template; up to 4,000 characters per input | 768 new tokens; deterministic | `.json` |
| [NewsScope](runtimes/newsscope/run.py) | English; standalone article template from author README | 2,000 new tokens; temperature 0.3; other settings inherited | `.json` |
| [Babelscape T5](runtimes/babelscape-t5/run.py) | English text directly; tokenizer from card | Checkpoint: five beams, minimum length 2, maximum length 250 | `.raw` |
| [ClaimPT](runtimes/claimpt/run.py) | Portuguese; 512-token windows, stride 128 | Token classification, no generation | Logits, input IDs and offsets in `.json` |
| [Principled 4B](runtimes/principled-4b/run.py) | Orbitals 0.6.1 prompt; string input becomes assistant message | SDK: 20,000 new tokens; sampling, temperature 0.7, top-p 0.8, top-k 20 | `.json` |
| [Principled 2B](runtimes/principled-2b/run.py) | Same Orbitals protocol | Same SDK settings | `.json` |
| [Dongyru Mistral](runtimes/dongyru-mistral/run.py) | Requires user-provided extraction prompt | Checkpoint/library configuration unless explicitly overridden | `.raw` |
| [FC-Claim-Det T5](runtimes/fc-claim-det-t5/run.py) | English; author P-MRR-HRR preprocessing | Six beams, no-repeat bigrams, minimum length 5, maximum length 15, early stopping | `.raw` |
| [SAGESSE](runtimes/sagesse-mistral/run.py) | Published Reddit template; explicitly empty submission/parent by default | Checkpoint/library configuration; no invented output budget | `.json` |
| [Mistral Instruct v0.2](runtimes/mistral-instruct-v02/run.py) | Requires user-provided extraction prompt | Checkpoint/library configuration unless explicitly overridden | `.raw` |

Source links are declared in each executor. Babelscape's generation limits come
from its checkpoint `generation_config.json`. FC-T5's maximum is `max_length=15`,
not `max_new_tokens=15`. Its original preprocessing retains the first mention or
hashtag of each consecutive run; it does not remove all mentions/hashtags.

Principled keeps the SDK defaults `skip_evidences=True` and no AI service
description. Its prompt disables thinking as the SDK does. The native Qwen3.5
conditional-generation class is used with text input to load the published
checkpoint on this Transformers version. The raw response is captured before
Orbitals parsing or JSON repair.

SAGESSE publishes an input template but no generation call with an output
budget. Its executor consequently inherits the checkpoint/library configuration.
That inherited configuration may be short; an incomplete output remains visible.

### Removed custom behavior

There is no built-in `GENERIC_PROMPT`. Detective no longer uses the custom
600-character/three-sentence partitioning, repetition penalty 1.1, string-field
bounds, lm-format-enforcer or JSON-closure stop rule. Its HF example does not
constrain JSON as the author's separate llama.cpp/GBNF example does.

Author defaults can still produce repeated, invalid or incomplete output.
Following those defaults does not guarantee extraction quality or valid JSON.

## Inputs and explicit overrides

The default generator input is the existing frozen English translation
`automatic.en.txt`. ClaimPT uses the original Portuguese `automatic.srt` after
caption indices and timestamps are removed. No runtime translation or ASR
correction is performed. English generators require an English TXT or SRT.

For one model, `--input` selects its input regardless of language. For a mixed
run, use `--input-en` and `--input-pt`; `--input` selects only English inputs.
The input is always your transcript, not the model card's example text.
NewsScope, Babelscape, FC-T5 and SAGESSE receive transcripts outside their
original news/summary/social-media/Reddit use cases; these are explicit input
adaptations, not reproduced author benchmarks.

Gemma processes the whole passage when it fits and only partitions when context
requires it. The existing seven-chunk APS file is used only when explicitly
passed with `--aps-input automatic.en.aps-input.jsonl`. Oversized inputs are
partitioned without discarding source text, including Detective inputs over
4,000 characters. Each input partition gets its own native model response.

There is no global 16,384-token context default. The context comes from the
model/tokenizer; `--context-tokens` is an optional ceiling. If the checkpoint
provides no usable context limit, the executor requests an explicit value.

Use `--max-new-tokens` or `--max-length` to override generation limits, never both:

```bash
uv run --frozen --project runtimes/detective-qwen3b \
  runtimes/detective-qwen3b/run.py --max-new-tokens 4096 \
  --output-dir results/detective-explicit-4096
```

The default is still 768. `--max-length` controls total sequence length; for a
causal model it includes the input. These overrides are recorded, not silently
applied. No sampling seed is forced; provide `--seed` when desired.

SAGESSE context can be supplied with `--submission-file` and
`--parent-comment-file`. Missing context remains empty as declared in its script.

### Models without published extraction prompts

Dongyru and Mistral Instruct require your own prompt file. The file is treated as
literal instructions, followed by the transcript, inside the model's chat
format. It is not a template language and no extra extraction instructions are
inserted.

```bash
uv run --frozen --project runtimes/dongyru-mistral \
  runtimes/dongyru-mistral/run.py --prompt-file /path/to/your-prompt.md \
  --output-dir results/user-prompt

uv run --frozen run_models.py --models all \
  --prompt-file dongyru-mistral=/path/to/dongyru-prompt.md \
  --prompt-file mistral-instruct-v02=/path/to/mistral-prompt.md \
  --output-dir results/all-with-user-prompts
```

Without these files, their status is `not_run`; no weights are downloaded for
them. Other selected models continue. The process returns a nonzero exit code
when any selected model is not run, fails or produces an incomplete response.

## Memory adaptations for cuba

Memory adaptations remain authorized and explicitly declared per executor:

- Gemma 2B, Detective and Principled 2B: FP16.
- Babelscape, FC-T5 and ClaimPT: FP32.
- Gemma 7B, NewsScope, Principled 4B and the Mistral models: NF4 first.
- Offload fallback keeps FP16 weights in CPU RAM and computes layers on CUDA.

These are RTX 2080 adaptations, not the authors' original precision settings.
Use `--precision` for an explicit override and `--no-offload-fallback` to disable
fallback. CUDA SDPA is selected when supported, with Flash SDP disabled for this
server. Default worker CPU threads are eight. Root sequential runs use Python
3.10; Torch 2.6.0/CUDA 12.4 remain pinned. Model-specific tokenizer, PEFT and
Orbitals dependencies are declared in each uv project.

NewsScope loads its base and adapter on CPU before attaching offload hooks.
PEFT does not automatically redistribute the base first; adapter autocasting is
disabled and small runtime buffers stay materialized. Babelscape and SAGESSE
include protobuf for tokenizer loading.

Staging reserves 5 GiB of disk and 8 GiB of RAM by default. No VRAM reserve is imposed.
If weights do not fit on disk, the supervisor can use an existing tmpfs such as
`/dev/shm`, accounting for loading memory as well. SAGESSE needs about 27 GiB of
weight staging. No mount or system configuration is created.

## Results

The output root is declared in each script or overridden with `--output-dir`.
The model alias is always appended:

```text
results/author-protocol/
  gemma-2b-aps/
    output.raw
    processing.json
  detective-qwen3b/
    output.json
    processing.json
```

Raw decoded responses are saved without JSON repair, claim normalization,
filtering or deduplication. Multiple JSON responses get `output-001.json`,
`output-002.json`, etc. Plain-text responses remain ordered in `output.raw`.
Generic models use `.raw` because a user prompt can request any output format.
No output defaults to `.txt` and no CSV summary is produced.

`processing.json` contains inference (including native-response decoding),
loading, download and total time; peak VRAM/RAM; CPU average/peak and CPU time;
temporary storage and output size. It also identifies protocol sources,
checkpoint revisions, effective generation settings, input path/hash and explicit
overrides. Failed attempts retain their phase, exception and traceback in this
same file. Runtime IPC and logs are temporary.

Times are seconds, memory/storage are GiB. CPU 100% approximates one logical CPU
core; it is not GPU utilization. VRAM is GPU process memory from NVML when
available, otherwise explicitly identified PyTorch allocated memory. Sampling is
once per second, so brief peaks may be missed. Tmpfs staging consumes system RAM.
Storage size and filesystem free space are measured only at the start and end
of each monitoring period. Storage peak fields are the maximum observed at those
boundaries and can miss intermediate peaks; CPU, RAM and VRAM keep one-second
sampling. Only running sums, counts and peaks are kept internally; individual
observations are discarded. Averages are sample means across valid worker
observations (including loading and all attempts), not energy consumption.
Unavailable averages are null; VRAM averages require NVML process measurements.

`success` means execution completed, not that the claims are correct. `partial`
means generation exhausted its budget without a stop token. Invalid JSON alone
does not turn a complete response into `partial`; JSON validity is reported
separately. `failed`, `interrupted` and `not_run` remain distinct statuses.

Existing results, including `results/all-models/`, are preserved. A nonempty
model result directory is never overwritten; use a new output root to compare
protocols. This refactor has not rerun model inference on cuba.
