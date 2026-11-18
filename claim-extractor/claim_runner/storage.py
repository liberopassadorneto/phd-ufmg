"""Persistent local storage shared by preparation and inference."""
import hashlib
import json
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def configure(root):
    root = Path(root).expanduser().resolve()
    # HF defaults its credential directory to XDG_CACHE_HOME/huggingface.
    # Preserve the login location before relocating application caches.
    original_cache = Path(os.environ.get('XDG_CACHE_HOME', '~/.cache')).expanduser()
    os.environ.setdefault('HF_HOME', str(original_cache / 'huggingface'))
    paths = {'UV_CACHE_DIR': 'cache/uv', 'UV_PYTHON_INSTALL_DIR': 'python',
             'XDG_CACHE_HOME': 'cache/xdg', 'TORCH_HOME': 'cache/torch',
             'TRITON_CACHE_DIR': 'cache/triton', 'CUDA_CACHE_PATH': 'cache/cuda',
             'PIP_CACHE_DIR': 'cache/pip', 'TMPDIR': 'tmp',
             'CLAIM_CHECKPOINT_CACHE': 'checkpoints', 'CLAIM_NLTK_DIR': 'cache/nltk'}
    for key, relative in paths.items():
        folder = root / relative
        folder.mkdir(parents=True, exist_ok=True)
        os.environ[key] = str(folder)
    for relative in ('results', 'venv', 'manifests', 'logs'):
        (root / relative).mkdir(parents=True, exist_ok=True)
    os.environ['UV_LINK_MODE'] = 'hardlink'
    tempfile.tempdir = str(root / 'tmp')
    return root


def runtime_stamp(root, spec):
    return Path(root) / 'manifests' / f'{spec.alias}.runtime.json'


def runtime_identity(project, python):
    return {'python': python, **{name: hashlib.sha256((project / name).read_bytes()).hexdigest()
                               for name in ('pyproject.toml', 'uv.lock')}}


def verify_runtime(root, spec, project, python):
    stamp = runtime_stamp(root, spec)
    env = Path(root) / 'venv' / spec.runtime
    if not (env / 'bin/python').exists() or not stamp.is_file():
        raise RuntimeError(f'Missing prepared runtime for {spec.alias}; run scripts/prepare-models.py')
    if json.loads(stamp.read_text()) != runtime_identity(project, python):
        raise RuntimeError(f'Prepared runtime changed for {spec.alias}; rerun scripts/prepare-models.py')
