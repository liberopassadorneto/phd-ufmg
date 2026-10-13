#!/usr/bin/env python3
"""Run mistralai/Mistral-7B-Instruct-v0.2; published protocol and cuba memory adaptations below."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from claim_runner.model import ModelSpec
from claim_runner.inputs import split_text
from claim_runner.runtime import (entrypoint, finish_loading, decode_generation,
                                  input_capacity, loading_options, stage)

# Input is an existing file, not a model-card example or an automatic translation.
DEFAULT_INPUT = ROOT / 'automatic.en.txt'
DEFAULT_OUTPUT = ROOT / 'results'
# Published generation arguments; all other values come from the checkpoint.
GENERATION = {}
# Explicit, authorized adaptations for RTX 2080 (8 GiB); not author defaults.
HARDWARE = {'precision': 'nf4', 'offload_fallback': True}
INPUT_CONFIGURATION = {'preparation': 'user-provided --prompt-file; no default extraction prompt', 'language': 'en'}
SPEC = ModelSpec(
    alias='mistral-instruct-v02', repo='mistralai/Mistral-7B-Instruct-v0.2', parameters_b=7.24,
    precision=HARDWARE['precision'], language='en',
    default_input=str(DEFAULT_INPUT), default_output=str(DEFAULT_OUTPUT),
    output_format='.raw', task='prompted_claim_extraction', causal=True,
    sources={'model_card': 'https://huggingface.co/mistralai/Mistral-7B-Instruct-v0.2'}, generation=GENERATION,
    base_repo=None, revision=None, requires_prompt=True,
    input_configuration=INPUT_CONFIGURATION, hardware_configuration=HARDWARE,
)

def load_model(job):
    from transformers import AutoTokenizer, AutoModelForCausalLM
    path = job['repositories'][0]['local_path']
    stage(job, 'loading_tokenizer')
    tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True, trust_remote_code=False)
    stage(job, 'loading_base')
    model = AutoModelForCausalLM.from_pretrained(path, **loading_options(AutoModelForCausalLM, path, job))
    return finish_loading(model, job), tokenizer


def render_input(text, tokenizer, job):
    # User supplies the instruction. No benchmark-authored default is inserted.
    if not job.get('prompt'):
        raise ValueError('This model requires --prompt-file')
    content = job['prompt'] + '\n\n' + text
    return tokenizer.apply_chat_template([{'role':'user', 'content':content}],
        tokenize=False, add_generation_prompt=True)


def prepare_chunks(job, model, tokenizer):
    source = job['input']['text']
    if not source:
        raise ValueError('Model preprocessing produced empty input')
    capacity = input_capacity(tokenizer, model, job, causal=True)
    return split_text(source, lambda text: len(tokenizer(render_input(text, tokenizer, job),
        add_special_tokens=False)['input_ids']) <= capacity,
        max_characters=None)


def infer(model, tokenizer, chunk, job):
    inputs = tokenizer(render_input(chunk['text'], tokenizer, job), return_tensors='pt',
        add_special_tokens=False).to('cuda')
    generated = model.generate(**inputs, generation_config=job['_generation'],
                               **job['_generation_overrides'])
    return decode_generation(tokenizer, generated, inputs, job, causal=True)


if __name__ == '__main__':
    try:
        raise SystemExit(entrypoint(SPEC, load_model, prepare_chunks, infer))
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as exc:
        print(f'ERROR: {type(exc).__name__}: {exc}', file=sys.stderr)
        raise SystemExit(1)
