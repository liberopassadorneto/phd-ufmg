"""Discover metadata from each model's run.py; no shared model configuration."""

import importlib.util
from functools import lru_cache
from pathlib import Path

ALIASES = (
    'gemma-2b-aps', 'gemma-7b-aps', 'detective-qwen3b', 'newsscope',
    'babelscape-t5', 'claimpt', 'principled-4b', 'principled-2b',
    'dongyru-mistral', 'fc-claim-det-t5', 'sagesse-mistral', 'mistral-instruct-v02',
)
ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=None)
def model_module(alias):
    path = ROOT / 'runtimes' / alias / 'run.py'
    spec = importlib.util.spec_from_file_location('claim_model_' + alias.replace('-', '_'), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODELS = tuple(model_module(alias).SPEC for alias in ALIASES)


def select_models(value):
    keys = [part.strip() for part in value.split(',')]
    if keys == ['all']:
        return list(MODELS)
    mapping = {key: model for model in MODELS for key in (model.alias, model.repo)}
    selected = []
    for key in keys:
        if key not in mapping:
            raise ValueError(f"Unknown model {key!r}. Use --list-models; 'all' must be used alone.")
        if mapping[key] not in selected:
            selected.append(mapping[key])
    return selected
