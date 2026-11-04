#!/usr/bin/env python3
"""Prepare checkpoints on Greenwich without loading models or CUDA."""
import argparse
import os
import tempfile
from pathlib import Path
from claim_runner.catalog import select_models
from claim_runner.downloads import repository_manifest, download_repositories
from claim_runner.prepared import publish

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--models', default='all')
parser.add_argument('--storage', type=Path, default=Path.home() / 'phd-models')
args = parser.parse_args()
root = args.storage.expanduser().resolve()
(root / 'checkpoints').mkdir(parents=True, exist_ok=True)
(root / 'tmp').mkdir(parents=True, exist_ok=True)
os.environ['CLAIM_CHECKPOINT_CACHE'] = str(root / 'checkpoints')
for spec in select_models(args.models):
    manifests = [repository_manifest(spec.repo, spec.revision)]
    if spec.base_repo:
        manifests.append(repository_manifest(spec.base_repo))
    with tempfile.TemporaryDirectory(dir=root / 'tmp', prefix='prepare-') as staging:
        records = download_repositories(manifests, Path(staging))
        publish(root, spec.alias, records)
    print(f'{spec.alias}: prepared', flush=True)
