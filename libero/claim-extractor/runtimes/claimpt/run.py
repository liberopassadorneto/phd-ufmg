#!/usr/bin/env python3
"""Run lfcc/bert-claimpt-chunk; published protocol and cuba memory adaptations below."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from claim_runner.model import ModelSpec
from claim_runner.runtime import (entrypoint, finish_loading,
                                  input_capacity, loading_options, stage)

# Input is an existing file, not a model-card example or an automatic translation.
DEFAULT_INPUT = ROOT / 'inputs' / 'automatic.srt'
DEFAULT_OUTPUT = ROOT / 'results'
# Published generation arguments; all other values come from the checkpoint.
GENERATION = {}
# Explicit, authorized adaptations for RTX 2080 (8 GiB); not author defaults.
HARDWARE = {'precision': 'fp32', 'offload_fallback': True}
INPUT_CONFIGURATION = {'preparation': 'Portuguese text; token windows', 'language': 'pt', 'max_tokens': 512, 'stride': 128}
SPEC = ModelSpec(
    alias='claimpt', repo='lfcc/bert-claimpt-chunk', parameters_b=0.109,
    precision=HARDWARE['precision'], language='pt',
    default_input=str(DEFAULT_INPUT), default_output=str(DEFAULT_OUTPUT),
    output_format='.json', task='claim_span_identification', causal=False,
    sources={'model_card': 'https://huggingface.co/lfcc/bert-claimpt-chunk'}, generation=GENERATION,
    base_repo=None, revision=None, requires_prompt=False,
    input_configuration=INPUT_CONFIGURATION, hardware_configuration=HARDWARE,
)

def load_model(job):
    from transformers import AutoTokenizer, AutoModelForTokenClassification
    path = job['repositories'][0]['local_path']
    stage(job, 'loading_tokenizer')
    tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True, trust_remote_code=False)
    stage(job, 'loading_base')
    model = AutoModelForTokenClassification.from_pretrained(path, **loading_options(AutoModelForTokenClassification, path, job))
    return finish_loading(model, job), tokenizer


def prepare_chunks(job, model, tokenizer):
    limit = min(INPUT_CONFIGURATION['max_tokens'], input_capacity(tokenizer, model, job, causal=False))
    if limit <= INPUT_CONFIGURATION['stride'] + tokenizer.num_special_tokens_to_add(pair=False):
        raise ValueError('ClaimPT context cannot accommodate its 128-token overlap')
    enc = tokenizer(job['input']['text'], return_tensors='pt', padding=True,
        truncation=True, max_length=limit, stride=INPUT_CONFIGURATION['stride'],
        return_overflowing_tokens=True, return_offsets_mapping=True)
    return [{'encoded': {k: v[i:i+1] for k, v in enc.items() if k in tokenizer.model_input_names},
             'offsets': enc['offset_mapping'][i].tolist()}
            for i in range(len(enc['input_ids']))]


def infer(model, tokenizer, chunk, job):
    inputs = {k: v.to('cuda') for k, v in chunk['encoded'].items()}
    logits = model(**inputs).logits
    return json.dumps({'logits': logits.float().cpu().tolist(),
                       'input_ids': inputs['input_ids'].cpu().tolist(),
                       'offsets': chunk['offsets']}, ensure_ascii=False), False


if __name__ == '__main__':
    try:
        raise SystemExit(entrypoint(SPEC, load_model, prepare_chunks, infer))
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as exc:
        print(f'ERROR: {type(exc).__name__}: {exc}', file=sys.stderr)
        raise SystemExit(1)
