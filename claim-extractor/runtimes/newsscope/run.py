#!/usr/bin/env python3
"""Run nidhipandya/NewsScope-lora; published protocol and cuba memory adaptations below."""

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
GENERATION = {'max_new_tokens': 2000, 'temperature': 0.3}
# Explicit, authorized adaptations for RTX 2080 (8 GiB); not author defaults.
HARDWARE = {'precision': 'nf4', 'offload_fallback': True}
INPUT_CONFIGURATION = {'preparation': 'author README article template', 'language': 'en', 'domain_adaptation': 'video transcript supplied as article'}
SPEC = ModelSpec(
    alias='newsscope', repo='nidhipandya/NewsScope-lora', parameters_b=8.03,
    precision=HARDWARE['precision'], language='en',
    default_input=str(DEFAULT_INPUT), default_output=str(DEFAULT_OUTPUT),
    output_format='.json', task='generative_claim_extraction', causal=True,
    sources={'model_card': 'https://huggingface.co/nidhipandya/NewsScope-lora', 'repository': 'https://github.com/nidhip1611/NewsScope', 'inference': 'https://github.com/nidhip1611/NewsScope/blob/main/README.md'}, generation=GENERATION,
    base_repo='meta-llama/Meta-Llama-3.1-8B-Instruct', revision=None, requires_prompt=False,
    input_configuration=INPUT_CONFIGURATION, hardware_configuration=HARDWARE,
)

def load_model(job):
    from transformers import AutoTokenizer, AutoModelForCausalLM
    path = job['repositories'][-1]['local_path']
    stage(job, 'loading_tokenizer')
    tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True, trust_remote_code=False)
    stage(job, 'loading_base')
    model = AutoModelForCausalLM.from_pretrained(path, **loading_options(AutoModelForCausalLM, path, job))
    from peft import PeftModel
    stage(job, 'loading_adapter')
    # Load adapter on the base device before attaching CPU offload hooks.
    model = PeftModel.from_pretrained(model, job['repositories'][0]['local_path'],
        local_files_only=True, is_trainable=False, low_cpu_mem_usage=False,
        autocast_adapter_dtype=False, torch_device='cpu' if job['mode'] == 'offload' else 'cuda:0')
    return finish_loading(model, job), tokenizer


def render_input(text, tokenizer, job):
    # Copied from the author's self-contained README example, not synthesized.
    return ('Extract structured claims from this news article.\n'
            'Return valid JSON with: domain, headline, key_points, whos_involved, '
            'how_it_unfolded, claims.\n\nArticle:\n' + text + '\n\nJSON Output:')


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
