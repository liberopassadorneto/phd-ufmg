#!/usr/bin/env python3
"""Run SAGESSE-EPFL/Mistral-7b-claims-extraction; published protocol and cuba memory adaptations below."""

import re
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
INPUT_CONFIGURATION = {'preparation': 'published README template', 'language': 'en', 'submission': '', 'parent_comment': '', 'domain_adaptation': 'video transcript supplied as comment'}
SPEC = ModelSpec(
    alias='sagesse-mistral', repo='SAGESSE-EPFL/Mistral-7b-claims-extraction', parameters_b=7.25,
    precision=HARDWARE['precision'], language='en',
    default_input=str(DEFAULT_INPUT), default_output=str(DEFAULT_OUTPUT),
    output_format='.json', task='generative_claim_extraction', causal=True,
    sources={'model_card': 'https://huggingface.co/SAGESSE-EPFL/Mistral-7b-claims-extraction'}, generation=GENERATION,
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
    readme = (Path(job['repositories'][0]['local_path']) / 'README.md').read_text(encoding='utf-8')
    fence = chr(96) * 3
    blocks = re.findall(fence + r'[^\n]*\n(.*?)' + fence, readme, flags=re.S)
    template = next((b for b in blocks if '### Instruction:' in b and '<input-comment>' in b), None)
    if template is None:
        raise ValueError('Published SAGESSE template was not found')
    return template.replace('<submission>', job.get('submission', INPUT_CONFIGURATION['submission'])).replace(
        '<parent-comment>', job.get('parent_comment', INPUT_CONFIGURATION['parent_comment'])).replace('<input-comment>', text)


def prepare_chunks(job, model, tokenizer):
    source = job['input']['text']
    if not source:
        raise ValueError('Model preprocessing produced empty input')
    capacity = input_capacity(tokenizer, model, job, causal=True)
    return split_text(source, lambda text: len(tokenizer(render_input(text, tokenizer, job),
        add_special_tokens=True)['input_ids']) <= capacity,
        max_characters=None)


def infer(model, tokenizer, chunk, job):
    inputs = tokenizer(render_input(chunk['text'], tokenizer, job), return_tensors='pt',
        add_special_tokens=True).to('cuda')
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
