"""Publish and verify immutable prepared checkpoints."""
import hashlib
import json
import os
from pathlib import Path


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def publish(root, alias, records):
    entries = []
    root = Path(root).resolve()
    for record in records:
        folder = Path(record['local_path']).resolve()
        files = []
        for item in record['files']:
            path = folder / item['name']
            if path.stat().st_size != item['bytes']:
                raise ValueError(f"Invalid size: {path}")
            files.append({**item, 'sha256': digest(path)})
        entries.append({'repo': record['repo'], 'revision': record['revision'],
                        'directory': str(folder.relative_to(root)), 'files': files})
    manifests = root / 'manifests'
    manifests.mkdir(parents=True, exist_ok=True)
    temp = manifests / f'.{alias}.{os.getpid()}.tmp'
    temp.write_text(json.dumps(entries, indent=2), encoding='utf-8')
    os.replace(temp, manifests / f'{alias}.json')


def load(root, spec, *, verify_hashes=False):
    root = Path(root).resolve()
    path = root / 'manifests' / f'{spec.alias}.json'
    if not path.is_file():
        raise RuntimeError(f'Missing prepared checkpoint for {spec.alias}; run prepare-models.py --storage with the selected models')
    records = json.loads(path.read_text(encoding='utf-8'))
    expected = [spec.repo] + ([spec.base_repo] if spec.base_repo else [])
    if [r['repo'] for r in records] != expected or (spec.revision and records[0]['revision'] != spec.revision):
        raise ValueError(f'Checkpoint manifest does not match {spec.alias}')
    for record in records:
        folder = (root / record['directory']).resolve()
        if not folder.is_relative_to(root) or not record['files']:
            raise ValueError('Invalid checkpoint directory or manifest')
        for item in record['files'] if verify_hashes else []:
            path = (folder / item['name']).resolve()
            if not path.is_relative_to(folder) or not path.is_file() or path.stat().st_size != item['bytes']:
                raise ValueError(f'Invalid prepared checkpoint file: {path}')
            if verify_hashes and digest(path) != item['sha256']:
                raise ValueError(f'Invalid prepared checkpoint file: {path}')
        record['local_path'] = str(folder)
    return records
