#!/usr/bin/env python3
"""Run Babelscape/t5-base-summarization-claim-extractor; published protocol and cuba memory adaptations below."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from claim_runner.model import ModelSpec
from claim_runner.inputs import split_text
from claim_runner.runtime import (entrypoint, finish_loading, decode_generation,
                                  input_capacity, loading_options, stage)

# Input is an existing file, not a model-card example or an automatic translation.
DEFAULT_INPUT = ROOT / 'inputs' / 'automatic.en.txt'
DEFAULT_OUTPUT = ROOT / 'results'
# Published generation arguments; all other values come from the checkpoint.
GENERATION = {}
# Explicit, authorized adaptations for RTX 2080 (8 GiB); not author defaults.
HARDWARE = {'precision': 'fp32', 'offload_fallback': True}
INPUT_CONFIGURATION = {'preparation': 'text', 'language': 'en', 'domain_adaptation': 'video transcript supplied directly; no summarizer'}
SPEC = ModelSpec(
    alias='babelscape-t5', repo='Babelscape/t5-base-summarization-claim-extractor', parameters_b=0.223,
    precision=HARDWARE['precision'], language='en',
    default_input=str(DEFAULT_INPUT), default_output=str(DEFAULT_OUTPUT),
    output_format='.raw', task='generative_claim_extraction', causal=False,
    sources={'model_card': 'https://huggingface.co/Babelscape/t5-base-summarization-claim-extractor', 'repository': 'https://github.com/Babelscape/FENICE'}, generation=GENERATION,
    base_repo=None, revision=None, requires_prompt=False,
    input_configuration=INPUT_CONFIGURATION, hardware_configuration=HARDWARE,
)

def load_model(job):
    from transformers import T5Tokenizer, T5ForConditionalGeneration
    path = job['repositories'][0]['local_path']
    stage(job, 'loading_tokenizer')
    tokenizer = T5Tokenizer.from_pretrained(path, local_files_only=True, trust_remote_code=False)
    stage(job, 'loading_base')
    model = T5ForConditionalGeneration.from_pretrained(path, **loading_options(T5ForConditionalGeneration, path, job))
    return finish_loading(model, job), tokenizer


def render_input(text, tokenizer, job):
    return text


def prepare_chunks(job, model, tokenizer):
    source = job['input']['text']
    if not source:
        raise ValueError('Model preprocessing produced empty input')
    capacity = input_capacity(tokenizer, model, job, causal=False)
    return split_text(source, lambda text: len(tokenizer(render_input(text, tokenizer, job),
        add_special_tokens=True)['input_ids']) <= capacity,
        max_characters=None)


def infer(model, tokenizer, chunk, job):
    inputs = tokenizer(render_input(chunk['text'], tokenizer, job), return_tensors='pt',
        add_special_tokens=True).to('cuda')
    generated = model.generate(**inputs, generation_config=job['_generation'],
                               **job['_generation_overrides'])
    return decode_generation(tokenizer, generated, inputs, job, causal=False)


if __name__ == '__main__':
    try:
        raise SystemExit(entrypoint(SPEC, load_model, prepare_chunks, infer))
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as exc:
        print(f'ERROR: {type(exc).__name__}: {exc}', file=sys.stderr)
        raise SystemExit(1)
