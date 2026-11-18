#!/usr/bin/env python3
"""Run Luimas/claim-extractor-detective-qwen3b; published protocol and cuba memory adaptations below."""

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
GENERATION = {'max_new_tokens': 768, 'do_sample': False}
# Explicit, authorized adaptations for RTX 2080 (8 GiB); not author defaults.
HARDWARE = {'precision': 'fp16', 'offload_fallback': True}
INPUT_CONFIGURATION = {'preparation': 'official prompt.txt plus tokenizer chat template', 'language': 'en', 'max_characters': 4000}
SPEC = ModelSpec(
    alias='detective-qwen3b', repo='Luimas/claim-extractor-detective-qwen3b', parameters_b=3.09,
    precision=HARDWARE['precision'], language='en',
    default_input=str(DEFAULT_INPUT), default_output=str(DEFAULT_OUTPUT),
    output_format='.json', task='generative_claim_extraction', causal=True,
    sources={'model_card': 'https://huggingface.co/Luimas/claim-extractor-detective-qwen3b', 'inference': 'https://huggingface.co/Luimas/claim-extractor-detective-qwen3b/blob/main/scripts/inference_hf.py'}, generation=GENERATION,
    base_repo=None, revision=None, requires_prompt=False,
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
    prompt = (Path(job['repositories'][0]['local_path']) / 'prompt.txt').read_text(encoding='utf-8')
    return tokenizer.apply_chat_template([{'role':'user', 'content':prompt + text}],
        tokenize=False, add_generation_prompt=True)


def prepare_chunks(job, model, tokenizer):
    job['_generation'].pad_token_id = tokenizer.eos_token_id
    source = job['input']['text']
    if not source:
        raise ValueError('Model preprocessing produced empty input')
    capacity = input_capacity(tokenizer, model, job, causal=True)
    return split_text(source, lambda text: len(tokenizer(render_input(text, tokenizer, job),
        add_special_tokens=False)['input_ids']) <= capacity,
        max_characters=INPUT_CONFIGURATION['max_characters'])


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
