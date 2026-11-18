#!/usr/bin/env python3
"""Prepare persistent checkpoints and locked dependencies without loading CUDA."""
import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from claim_runner.catalog import select_models
from claim_runner.downloads import repository_manifest, download_repositories
from claim_runner.prepared import publish, load
from claim_runner.resources import GIB
from claim_runner.storage import configure, ROOT, runtime_identity, runtime_stamp


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--models', default='all')
    parser.add_argument('--storage', type=Path, default=Path.home() / 'phd-models')
    parser.add_argument('--python', default='3.10')
    parser.add_argument('--disk-reserve-gib', type=float, default=5)
    parser.add_argument('--checkpoints-only', action='store_true', help='Legacy checkpoint-only preparation')
    args = parser.parse_args()
    if args.disk_reserve_gib < 0:
        parser.error('Disk reserve must be nonnegative')
    root = configure(args.storage)
    reserve = args.disk_reserve_gib * GIB
    selected = select_models(args.models)
    plans, unique = {}, {}
    for spec in selected:
        try:
            records = load(root, spec, verify_hashes=True)
        except (FileNotFoundError, RuntimeError):
            records = []
            for repo, revision in [(spec.repo, spec.revision)] + ([(spec.base_repo, None)] if spec.base_repo else []):
                key = (repo, revision)
                if key not in unique:
                    unique[key] = repository_manifest(repo, revision)
                records.append(unique[key])
        plans[spec.alias] = records
    needed = {}
    for records in plans.values():
        for record in records:
            needed[(record['repo'], record['revision'])] = record
    # Count existing files, including resumable downloads, only when sizes match.
    import hashlib
    missing = 0
    for record in needed.values():
        key = hashlib.sha256((record['repo'] + '@' + record['revision']).encode()).hexdigest()
        for item in record['files']:
            path = root / 'checkpoints' / key / item['name']
            if not path.is_file() or path.stat().st_size != item['bytes']:
                missing += item['bytes']
    print(f'Checkpoint download estimate: {missing / GIB:.2f} GiB; free: '
          f'{shutil.disk_usage(root).free / GIB:.2f} GiB; reserve: {args.disk_reserve_gib} GiB', flush=True)
    print('Dependency space is additional; uv cache and environments share files via hardlinks.', flush=True)
    if shutil.disk_usage(root).free < missing + reserve:
        raise RuntimeError('Insufficient disk for selected checkpoints plus reserve; select fewer models')
    failures = []
    for spec in selected:
        try:
            if not args.checkpoints_only:
                if shutil.disk_usage(root).free < reserve + 4 * GIB:
                    raise RuntimeError('Insufficient disk for dependency installation plus reserve')
                environment = os.environ.copy()
                environment['UV_PROJECT_ENVIRONMENT'] = str(root / 'venv' / spec.runtime)
                project = ROOT / 'runtimes' / spec.runtime
                with (root / 'logs' / f'prepare-{spec.alias}.log').open('w') as log:
                    subprocess.run(['uv', 'sync', '--frozen', '--project', str(project), '--python', args.python],
                                   env=environment, stdout=log, stderr=subprocess.STDOUT, check=True)
                stamp = runtime_stamp(root, spec)
                temp = stamp.with_suffix('.tmp')
                temp.write_text(json.dumps(runtime_identity(project, args.python)))
                os.replace(temp, stamp)
            records = plans[spec.alias]
            if not all('local_path' in r for r in records):
                with tempfile.TemporaryDirectory(dir=root / 'tmp', prefix='prepare-') as staging:
                    records = download_repositories(records, Path(staging), reserve_bytes=reserve)
                    publish(root, spec.alias, records)
            print(f'{spec.alias}: prepared', flush=True)
        except Exception as exc:
            failures.append(f'{spec.alias}: {exc}')
            print(failures[-1], flush=True)
    if not args.checkpoints_only and any(s.alias.startswith('gemma-') for s in selected):
        import nltk
        if not nltk.download('punkt_tab', download_dir=str(root / 'cache/nltk'), quiet=True):
            failures.append('NLTK punkt_tab preparation failed')
    if failures:
        raise RuntimeError('\n'.join(failures))


if __name__ == '__main__':
    main()
