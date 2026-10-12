---
license: apache-2.0
base_model: unsloth/Qwen2.5-3B-Instruct-bnb-4bit
language: [en]
library_name: transformers
pipeline_tag: text-generation
tags: [claim-extraction, fact-checking, misinformation, contradiction-detection, sarcasm-detection, json, grammar-constrained, qlora, unsloth, gguf]
---

# Claim Extractor — detective fact-checker (Qwen2.5-3B, distilled from 14B)

A small, **local** model that reads English text and emits **strict, machine-readable JSON**: a summary,
keywords, a publication date (if present), a list of **atomic claims** (each typed, categorized,
stance/sentiment-tagged, anchored to verbatim evidence, with investigative **fact-checking questions**),
and the **contradictions** between claims. Built as the structured front-end of a rumor /
misinformation-detection pipeline. **This repository is fully self-contained** — model, tokenizer, GGUF,
grammar, prompt, schema, corpus, benchmarks, and scripts are all here; nothing else is required.

- **Student:** `unsloth/Qwen2.5-3B-Instruct-bnb-4bit` (QLoRA fine-tune) → **Q4_K_M GGUF (~2 GB)** that runs on a **4 GB GPU** or CPU, offline.
- **Teacher (distillation):** `Qwen/Qwen2.5-14B-Instruct`.
- **Always-valid JSON:** a GBNF grammar (`claim.gbnf`) constrains decoding → parseable on 100% of inputs.
- **English only. No truth verdicts** — it surfaces *what to check*, not whether a claim is true.

## Features and capabilities
- Claim extraction (explicit + implicit), compound-sentence decomposition, brief paraphrased claims.
- Typing (`fact/statistic/opinion/prediction/speculation/rhetoric/other`), stance
  (`asserted/denied/hedged/attributed/ironic`), sentiment (`positive/negative/neutral/mixed`).
- Verbatim evidence anchoring; contradiction & statistical-consistency detection (`contradiction`/`tension`).
- Sarcasm/irony handling (restates real meaning, `ironic` stance + `tension` link).
- 3–6 investigative **verification questions** per claim; metadata (summary, date-if-present, keywords).

## Repository layout
```
README.md                       this file
config.json / *.safetensors     merged fp16 model (HF format, at repo root)
generation_config.json
tokenizer.json / tokenizer_config.json / vocab.json / merges.txt / special_tokens_map.json
Qwen2.5-3B-Instruct.Q4_K_M.gguf                         quantized model for llama.cpp (4 GB GPU / CPU)
claim.gbnf                       grammar that guarantees valid JSON
prompt.txt                       system prompt / task instruction
schema.json                     output schema + label mappings (enums)
requirements.txt                dependencies
LICENSE
lora_adapter/                   LoRA adapter only
scripts/   inference.py  inference_hf.py  evaluate.py
benchmarks/  benchmarks.json  benchmark_comparison.md  base/teacher/finetuned scores
corpus/    labeled.jsonl  converted.jsonl  DATASET_MANIFEST.json  CORPUS.md
training/  train_config.json  RUN_SUMMARY.json
```

## Installation
```bash
pip install -r requirements.txt
# GGUF path needs only: pip install llama-cpp-python   (add a CUDA wheel index for GPU)
```

## Quick start (grammar-constrained → always-valid JSON)
```bash
python -c "from huggingface_hub import snapshot_download; snapshot_download('Luimas/claim-extractor-detective-qwen3b', local_dir='claimx')"
cd claimx
python scripts/inference.py --text "The mayor said crime fell; hours later the chief said it rose."
```

## Usage examples
**llama.cpp (Python):**
```python
import json, glob
from llama_cpp import Llama, LlamaGrammar
llm = Llama(model_path=glob.glob("*.gguf")[0], n_ctx=4096, n_gpu_layers=-1, verbose=False)
prompt = open("prompt.txt").read(); grammar = LlamaGrammar.from_string(open("claim.gbnf").read())
out = llm.create_chat_completion(messages=[{"role":"user","content":prompt+"YOUR TEXT"}],
                                 grammar=grammar, temperature=0.0, max_tokens=768)
print(json.loads(out["choices"][0]["message"]["content"]))
```
**Transformers (merged fp16):** `python scripts/inference_hf.py --text "..."` (loads this repo directly).

## Input and output formats
- **Input:** one block of English text (news, social post, review, press release, sarcastic/adversarial prose);
  prepend `prompt.txt`. Truncated to ~4000 chars.
- **Output:** exactly one JSON object (no prose), schema below.

## Output schema
```json
{
  "summary": "<1-3 sentence neutral summary>",
  "publication_date": "<ISO date if present, else null>",
  "keywords": ["<3-12 terms>"],
  "claims": [{
    "id": 0, "claim": "<brief paraphrase>",
    "claim_type": "fact|statistic|opinion|prediction|speculation|rhetoric|other",
    "category": "<topic>", "importance": "high|medium|low",
    "stance": "asserted|denied|hedged|attributed|ironic",
    "sentiment": "positive|negative|neutral|mixed",
    "evidence_span": "<verbatim substring>", "confidence": 0.0,
    "verification_questions": ["<3-6 investigative questions>"]
  }],
  "contradictions": [{"claim_a": 0, "claim_b": 1, "relation": "contradiction|tension", "explanation": "<why>"}]
}
```
Full enum/label mappings are in `schema.json`. Guarantees: always-valid JSON; `keywords`/`claims`
non-empty; ids `0..n-1`; no duplicate claims; `evidence_span` verbatim; ≥3 verification questions/claim;
contradictions reference real ids.

## Fine-tuning details
Knowledge distillation + **QLoRA** (4-bit base, fp16 adapters) with Unsloth on Kaggle (2× T4). The
`Qwen/Qwen2.5-14B-Instruct` teacher labels passages into the schema; the `unsloth/Qwen2.5-3B-Instruct-bnb-4bit` student learns to reproduce it.
Best checkpoint kept by eval-loss; data balanced per source with hand-authored gold examples upweighted.
Full hyper-parameters in `training/train_config.json`; run details in `training/RUN_SUMMARY.json`.

## Training dataset
Bundled under `corpus/` (self-contained): `labeled.jsonl` (teacher-labeled + hand-authored **gold**
examples) + `converted.jsonl` (SNLI/MNLI/ANLI/FEVER/LIAR templated). See `corpus/CORPUS.md` and
`corpus/DATASET_MANIFEST.json`. Trained on ~1471 examples (val ~127).

## Benchmarks and evaluation
Base vs teacher vs fine-tuned on a fixed diverse test set (`benchmarks/benchmarks.json`,
`benchmark_comparison.md`). Fine-tuned highlights:

| Metric | Base | Fine-tuned |
|---|---|---|
| JSON validity | 1.0 | 1.0 |
| Verification-questions / claim | — | 3 |
| Contradiction recall | — | 0.75 |
| Sarcasm handling | — | 1.0 |
| Evidence-verbatim rate | — | 1.0 |
| Avg claim length (words) | — | 7.806 |

Held-out validity: 1.0.  Re-run locally: `python scripts/evaluate.py`.

## Deployment (RTX 3050 4 GB or CPU, offline)
The three files needed are **`Qwen2.5-3B-Instruct.Q4_K_M.gguf` + `claim.gbnf` + `prompt.txt`**.
```bash
pip install llama-cpp-python   # CUDA: --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124
python scripts/inference.py --text "Paste any English paragraph."
```
Grammar-constrained decoding guarantees valid JSON on every call.

## Limitations
English only. No truth/veracity verdicts (surfaces what to verify, not whether it is true). It is a
structured extractor, not a chat assistant. Evidence spans are verbatim from the input; if the input is
wrong, the extracted claim reflects that. Distilled from a 14B teacher — quality is bounded by it.

## Citation
```bibtex
@misc{claim_extractor_qwen3b,
  title  = {Claim Extractor: a local, grammar-constrained claim-extraction model (Qwen2.5-3B, QLoRA)},
  author = {Luimas},
  year   = {2026},
  note   = {Hugging Face: Luimas/claim-extractor-detective-qwen3b}
}
```

## License
Apache-2.0 (see `LICENSE`). Inherits the license terms of the base model `unsloth/Qwen2.5-3B-Instruct-bnb-4bit`.
