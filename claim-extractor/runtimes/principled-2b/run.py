#!/usr/bin/env python3
"""Run principled-intelligence/claim-extractor-2B-q-2605; published protocol and cuba memory adaptations below."""

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
GENERATION = {'max_new_tokens': 20000, 'do_sample': True, 'temperature': 0.7, 'repetition_penalty': 1.0, 'top_p': 0.8, 'top_k': 20, 'min_p': 0.0}
# Explicit, authorized adaptations for RTX 2080 (8 GiB); not author defaults.
HARDWARE = {'precision': 'fp16', 'offload_fallback': True}
INPUT_CONFIGURATION = {'preparation': 'Orbitals build_prompt', 'language': 'en', 'message_role': 'assistant', 'ai_service_description': None, 'skip_evidences': True}
SPEC = ModelSpec(
    alias='principled-2b', repo='principled-intelligence/claim-extractor-2B-q-2605', parameters_b=2.27,
    precision=HARDWARE['precision'], language='en',
    default_input=str(DEFAULT_INPUT), default_output=str(DEFAULT_OUTPUT),
    output_format='.json', task='generative_claim_extraction', causal=True,
    sources={'model_card': 'https://huggingface.co/principled-intelligence/claim-extractor-2B-q-2605', 'repository': 'https://github.com/Principled-Intelligence/orbitals', 'inference': 'https://github.com/Principled-Intelligence/orbitals/blob/v0.6.1/src/hf_pipeline/claim_extractor.py'}, generation=GENERATION,
    base_repo=None, revision=None, requires_prompt=False,
    input_configuration=INPUT_CONFIGURATION, hardware_configuration=HARDWARE,
)

def load_model(job):
    from transformers import AutoTokenizer, Qwen3_5ForConditionalGeneration
    path = job['repositories'][0]['local_path']
    stage(job, 'loading_tokenizer')
    tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True, trust_remote_code=False)
    stage(job, 'loading_base')
    model = Qwen3_5ForConditionalGeneration.from_pretrained(path, **loading_options(Qwen3_5ForConditionalGeneration, path, job))
    return finish_loading(model, job), tokenizer


def render_input(text, tokenizer, job):
    from orbitals.claim_extractor.prompting import build_prompt
    # String input becomes an assistant message; skip_evidences=True is the SDK default.
    return build_prompt(tokenizer, text, ai_service_description=INPUT_CONFIGURATION['ai_service_description'],
        skip_evidences=INPUT_CONFIGURATION['skip_evidences'])


def prepare_chunks(job, model, tokenizer):
    tokenizer.padding_side = 'left'
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
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
