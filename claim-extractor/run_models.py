#!/usr/bin/env python3
"""Run the claim-extractor checkpoint catalog sequentially on the CUDA server."""

from __future__ import annotations

import argparse
import copy
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import time
import tempfile
import uuid
from pathlib import Path

from claim_runner.catalog import MODELS, select_models
from claim_runner.downloads import download_repositories, repository_manifest
from claim_runner.prepared import load as load_prepared
from claim_runner.inputs import read_transcript
from claim_runner.storage import configure, verify_runtime
from claim_runner.outputs import export_result
from claim_runner.resources import (GIB, Monitor, choose_staging, cleanup_staging,
                                    create_staging, directory_size, write_json)

ROOT = Path(__file__).resolve().parent


def parse_args(argv=None, model_alias=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", default=model_alias or "all", help="Comma-separated aliases/HF IDs or all")
    parser.add_argument("--list-models", action="store_true")
    parser.add_argument("--check", action="store_true", help="Install/check runtimes and CUDA; do not download models")
    parser.add_argument("--input", type=Path, help="Transcript for one model; English input in mixed runs")
    parser.add_argument("--input-en", type=Path, help="English video transcript (.txt or .srt)")
    parser.add_argument("--input-pt", type=Path, help="Portuguese input for ClaimPT")
    parser.add_argument("--aps-input", type=Path, help="Explicit frozen APS JSONL; not selected automatically")
    parser.add_argument("--prompt-file", action="append", default=[], metavar="ALIAS=PATH",
                        help="User prompt; repeat ALIAS=PATH for multiple models, or PATH for one model")
    parser.add_argument("--submission-file", type=Path, help="Optional SAGESSE submission context")
    parser.add_argument("--parent-comment-file", type=Path, help="Optional SAGESSE parent comment context")
    parser.add_argument("--output-dir", type=Path, help="Results root; defaults to each model's DEFAULT_OUTPUT")
    parser.add_argument("--staging-dir", type=Path, default=ROOT / ".model-staging")
    parser.add_argument("--storage", type=Path, help="Persistent local checkpoints, dependencies, caches and results")
    parser.add_argument("--remote-storage", type=Path, help="SSHFS mount for persistent checkpoints, environments and results")
    parser.add_argument("--offline", action="store_true", help="Use prepared checkpoints; local storage also requires prepared dependencies")
    parser.add_argument("--ram-staging-dir", type=Path, default=Path("/dev/shm"))
    parser.add_argument("--runtime-dir", type=Path, default=ROOT / "runtimes")
    parser.add_argument("--python", default=f"{sys.version_info.major}.{sys.version_info.minor}" if model_alias else "3.10",
                        help="Worker Python; direct executors use their current interpreter version")
    parser.add_argument("--precision", choices=("auto", "fp16", "fp32", "nf4", "offload"), default="auto")
    parser.add_argument("--no-offload-fallback", action="store_true")
    parser.add_argument("--disk-reserve-gib", type=float, default=5)
    parser.add_argument("--ram-reserve-gib", type=float, default=8)
    parser.add_argument("--gpu-reserve-gib", type=float, default=0,
                        help="Deprecated compatibility option; no VRAM reserve is enforced")
    parser.add_argument("--context-tokens", type=int,
                        help="Explicit context ceiling; default comes from the model/tokenizer")
    limits = parser.add_mutually_exclusive_group()
    limits.add_argument("--max-new-tokens", type=int, help="Explicit override of published generation budget")
    limits.add_argument("--max-length", type=int, help="Explicit total sequence-length override")
    parser.add_argument("--cpu-threads", type=int, default=8)
    parser.add_argument("--seed", type=int, help="Optional sampling seed; no forced seed by default")
    parser.add_argument("--model-timeout", type=float, default=0,
                        help="Seconds per worker attempt; 0 disables timeout")
    args = parser.parse_args(argv)
    if args.storage and args.remote_storage:
        parser.error("--storage and --remote-storage are mutually exclusive")
    if args.offline and not (args.storage or args.remote_storage):
        parser.error("--offline requires --storage or --remote-storage")
    for name in ("disk_reserve_gib", "ram_reserve_gib", "gpu_reserve_gib", "model_timeout"):
        if getattr(args, name) < 0:
            parser.error(f"--{name.replace('_', '-')} must be nonnegative")
    if args.cpu_threads < 1 or any(value is not None and value < 1 for value in
            (args.context_tokens, args.max_new_tokens, args.max_length)):
        parser.error("Token limits and CPU threads must be positive")
    try:
        args.selected = select_models(args.models)
    except ValueError as exc:
        parser.error(str(exc))
    if model_alias and [spec.alias for spec in args.selected] != [model_alias]:
        parser.error("A model's run.py executes only that model; use run_models.py for a sequence")
    if model_alias and args.python != f"{sys.version_info.major}.{sys.version_info.minor}":
        parser.error("Select the interpreter with uv run --python before run.py, rather than replacing its active environment")
    args.prompts = {}
    for value in args.prompt_file:
        if "=" in value:
            alias, filename = value.split("=", 1)
        elif len(args.selected) == 1:
            alias, filename = args.selected[0].alias, value
        else:
            parser.error("--prompt-file requires ALIAS=PATH when selecting multiple models")
        matching = [spec for spec in args.selected if alias in (spec.alias, spec.repo)]
        if len(matching) != 1 or not matching[0].requires_prompt:
            parser.error(f"{alias}: --prompt-file is only for selected models without a published extraction prompt")
        alias = matching[0].alias
        if alias in args.prompts:
            parser.error(f"Duplicate --prompt-file for {alias}")
        path = Path(filename).resolve()
        try:
            prompt = path.read_text(encoding="utf-8")
        except OSError as exc:
            parser.error(str(exc))
        if not prompt.strip():
            parser.error(f"Empty prompt file: {path}")
        args.prompts[alias] = {"prompt": prompt, "prompt_file": str(path)}
    args.context_files = {}
    for option in ("submission_file", "parent_comment_file"):
        path = getattr(args, option)
        if path is not None:
            if not any(spec.alias == "sagesse-mistral" for spec in args.selected):
                parser.error("Context files apply only to SAGESSE")
            try:
                args.context_files[option] = str(path.resolve())
                args.context_files[option.removesuffix("_file")] = path.read_text(encoding="utf-8")
            except OSError as exc:
                parser.error(str(exc))
    for spec in args.selected:
        maximum = args.max_new_tokens or spec.generation.get("max_new_tokens")
        if spec.causal and args.context_tokens and maximum and maximum >= args.context_tokens and args.max_length is None:
            parser.error(f"{spec.alias}: --context-tokens must exceed its {maximum}-token output budget")
    return args


def stop_process(process):
    if process.poll() is not None:
        return
    os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()


def command_record(command, output, timeout=0, staging=None, env=None):
    output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    monitor = Monitor(output / "resource-samples.jsonl", staging, output / "phase.json").start()
    process = None
    record = {"command": command}
    try:
        with (output / "process.log").open("w", encoding="utf-8") as log:
            process = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                       start_new_session=True, env=env)
            monitor.attach(process.pid)
            try:
                record["returncode"] = process.wait(timeout=timeout or None)
            except subprocess.TimeoutExpired:
                stop_process(process)
                record.update(returncode=process.returncode, timed_out=True)
    finally:
        if process is not None:
            stop_process(process)
        record["wall_seconds"] = time.perf_counter() - started
        record["resources"] = monitor.stop()
        write_json(output / "process-result.json", record)
    return record


def worker_command(args, spec, *extra):
    return ["uv", "run", "--frozen", "--no-sync", "--project",
            str((args.runtime_dir / spec.runtime).resolve()), "--python", args.python,
            "python", str((args.runtime_dir / spec.runtime / "run.py").resolve()), *map(str, extra)]


def runtime_environment(args, spec):
    env = os.environ.copy()
    storage = args.storage or args.remote_storage
    if storage:
        env['UV_PROJECT_ENVIRONMENT'] = str(storage / 'venv' / spec.runtime)
    if args.storage and args.offline:
        env.update(UV_OFFLINE='1', UV_PYTHON_DOWNLOADS='never', CLAIM_OFFLINE='1')
    return env


def ensure_runtime(args, spec, run_dir, cache):
    if spec.runtime not in cache:
        folder = run_dir / "preflight" / spec.runtime
        project = args.runtime_dir / spec.runtime
        environment = runtime_environment(args, spec)
        prepared = args.storage and args.offline
        if args.check and prepared:
            verify_runtime(args.storage, spec, project, args.python)
        print(f"{'Using prepared runtime' if prepared else 'Preparing uv runtime'}: {spec.runtime}", flush=True)
        setup = {"returncode": 0, "prepared": True} if args.storage and args.offline else command_record(["uv", "sync", "--frozen", "--project", str(project.resolve()),
                                "--python", args.python], folder / "setup", env=environment)
        if setup["returncode"] != 0:
            raise RuntimeError(f"Runtime setup failed; see {folder / 'setup/process.log'}")
        cache[spec.runtime] = {"setup": setup, "folder": str(folder)}
    state = cache[spec.runtime]
    if args.check:
        if "cuda" not in state:
            probe_dir = Path(state["folder"]) / "cuda"
            probe_dir.mkdir(parents=True, exist_ok=True)
            state["cuda"] = command_record(worker_command(args, spec, "--probe", probe_dir / "cuda.json"),
                                           probe_dir, timeout=120, env=runtime_environment(args, spec))
        if state["cuda"]["returncode"] != 0:
            raise RuntimeError(f"CUDA/FP16 preflight failed; see {state['folder']}/cuda/process.log")
    return state


def ensure_quantization(args, spec, state):
    if "nf4" not in state:
        folder = Path(state["folder"]) / "nf4"
        folder.mkdir(parents=True, exist_ok=True)
        state["nf4"] = command_record(worker_command(args, spec, "--probe", folder / "nf4.json", "--quantized"),
                                      folder, timeout=120, env=runtime_environment(args, spec))
    return state["nf4"]["returncode"] == 0


def prepare_inputs(args):
    inputs = {}
    for spec in args.selected:
        if spec.requires_prompt and spec.alias not in args.prompts:
            continue
        path = args.input_pt if spec.language == "pt" else args.input_en
        if path is None and args.input is not None and (len(args.selected) == 1 or spec.language == "en"):
            path = args.input
        inputs[spec.alias] = read_transcript(path or Path(spec.default_input))
    return inputs, str(args.aps_input.resolve()) if args.aps_input else None


def run_one(args, spec, run_dir, inputs, aps, runtimes):
    output = run_dir / spec.alias
    output.mkdir()
    started = time.perf_counter()
    owner = uuid.uuid4().hex
    staging = parent = None
    record = {"cpu_threads": args.cpu_threads, "alias": spec.alias, "model": spec.record(), "status": "failed", "attempts": [],
              "download_seconds": 0.0, "cleanup_seconds": 0.0}
    record["configuration"] = {
        "sources": spec.sources, "declared_generation": spec.generation,
        "input": spec.input_configuration, "hardware": spec.hardware_configuration,
        "overrides": {key: getattr(args, key) for key in
                      ("max_new_tokens", "max_length", "context_tokens", "seed")
                      if getattr(args, key) is not None},
    }
    if spec.alias in inputs:
        record["configuration"].update(input_file=inputs[spec.alias]["path"],
                                       input_sha256=inputs[spec.alias]["sha256"])
    if spec.requires_prompt and spec.alias not in args.prompts:
        record.update(status="not_run", total_seconds=0.0,
                      error="No published extraction prompt; supply --prompt-file for this model")
        print(f"{spec.alias}: not_run — {record['error']}", flush=True)
        return record
    try:
        preflight_started = time.perf_counter()
        ensure_runtime(args, spec, run_dir, runtimes)
        mode = spec.precision if args.precision == "auto" else args.precision
        if not spec.causal and mode == "nf4":
            raise ValueError("NF4 override is supported only for the causal language models")
        record["preflight_seconds"] = time.perf_counter() - preflight_started
        persistent_ready = False
        if args.storage and not args.offline:
            try:
                manifests = load_prepared(args.storage, spec)
                persistent_ready = True
            except (FileNotFoundError, RuntimeError):
                pass
        if args.offline or persistent_ready:
            verification_started = time.perf_counter()
            manifests = load_prepared(args.storage or args.remote_storage, spec)
            record['checkpoint_verification_seconds'] = time.perf_counter() - verification_started
        else:
            manifests = [repository_manifest(spec.repo, spec.revision)]
            if spec.base_repo:
                manifests.append(repository_manifest(spec.base_repo))
        record["configuration"]["repositories"] = [
            {"repo": manifest["repo"], "revision": manifest["revision"]} for manifest in manifests]
        download_bytes = 0 if args.offline or persistent_ready else sum(m["download_bytes"] for m in manifests)
        # Include CPU loading/conversion buffers and room for a fallback attempt.
        memory_bytes = int(spec.parameters_b * 1e9 * 2 * 1.35) + 3 * GIB
        parent, storage_kind = choose_staging(download_bytes, memory_bytes, args.staging_dir.resolve(),
                                              args.ram_staging_dir.resolve(), int(args.disk_reserve_gib * GIB),
                                              int(args.ram_reserve_gib * GIB))
        staging = create_staging(parent, owner)
        record.update(staging=str(staging), staging_kind=storage_kind,
                      download_bytes=download_bytes, estimated_worker_ram_bytes=memory_bytes)
        print(f"{spec.alias}: {download_bytes / GIB:.2f} GiB download, staging={storage_kind}, mode={mode}", flush=True)
        before = time.perf_counter()
        monitor = Monitor(output / "download-resources.jsonl", staging).start()
        monitor.phase = "download"
        monitor.attach(os.getpid())
        try:
            repositories = manifests if args.offline or persistent_ready else download_repositories(
                manifests, staging, reserve_bytes=int(args.disk_reserve_gib * GIB))
            if args.storage and not args.offline and not persistent_ready:
                from claim_runner.prepared import publish
                publish(args.storage, spec.alias, repositories)
            record["persistent_checkpoints"] = bool(args.storage or args.remote_storage)
        finally:
            record["download_seconds"] = time.perf_counter() - before
            record["download_resources"] = monitor.stop()
        record["staging_peak_bytes"] = directory_size(staging)
        environment = runtime_environment(args, spec)
        environment.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
                           HF_HOME=str(staging / "hf-home"), HF_XET_CACHE=str(staging / "xet"),
                           HF_HUB_DISABLE_XET="1", TOKENIZERS_PARALLELISM="false",
                           OMP_NUM_THREADS=str(args.cpu_threads), MKL_NUM_THREADS=str(args.cpu_threads),
                           PYTHONPATH=str(ROOT))
        for attempt_number in (1, 2):
            import psutil
            if psutil.virtual_memory().available < memory_bytes + int(args.ram_reserve_gib * GIB):
                raise RuntimeError("RAM budget no longer fits after staging; preserving results and cleaning weights")
            attempt_dir = output / f"attempt-{attempt_number}-{mode}"
            attempt_dir.mkdir()
            write_json(attempt_dir / "job.json", {
                "spec": spec.record(), "repositories": repositories, "mode": mode,
                "input": inputs[spec.alias], "aps_input": aps, "output": str(attempt_dir.resolve()),
                "seed": args.seed, "cpu_threads": args.cpu_threads,
                "context_tokens": args.context_tokens, "max_new_tokens": args.max_new_tokens,
                "max_length": args.max_length, **args.prompts.get(spec.alias, {}),
                **(args.context_files if spec.alias == "sagesse-mistral" else {})})
            attempt = command_record(worker_command(args, spec, "--job", attempt_dir / "job.json"),
                                     attempt_dir, args.model_timeout, staging, environment)
            worker_path = attempt_dir / "worker-result.json"
            worker = json.loads(worker_path.read_text()) if worker_path.exists() else {
                "status": "failed", "error": f"Worker exited with code {attempt['returncode']} before writing a result; see process.log"}
            attempt.update(directory=str(attempt_dir), mode=mode, worker=worker)
            record["attempts"].append(attempt)
            record["status"] = worker["status"] if attempt["returncode"] == 0 else (
                "partial" if worker["status"] == "partial" else "failed")
            if record["status"] != "failed":
                record["selected_attempt"] = str(attempt_dir)
                break
            retry = worker.get("retry_with_offload") or attempt["returncode"] in (42, -signal.SIGILL)
            if (attempt.get("timed_out") or args.no_offload_fallback or
                    not spec.hardware_configuration.get("offload_fallback", True) or
                    mode in ("offload", "fp32") or not retry):
                break
            print(f"{spec.alias}: retrying with RAM weight offload; first attempt preserved", flush=True)
            mode = "offload"
        record["load_seconds"] = sum(a["worker"].get("load_seconds", 0) for a in record["attempts"])
        record["inference_seconds"] = sum(a["worker"].get("inference_seconds", 0) for a in record["attempts"])
    except KeyboardInterrupt:
        record.update(status="interrupted", error="Interrupted by signal or keyboard")
        if "attempt_dir" in locals() and not any(
                a["directory"] == str(attempt_dir) for a in record["attempts"]):
            worker_path = attempt_dir / "worker-result.json"
            result_path = attempt_dir / "process-result.json"
            attempt = json.loads(result_path.read_text()) if result_path.exists() else {"resources": {}}
            worker = json.loads(worker_path.read_text()) if worker_path.exists() else {}
            attempt.update(directory=str(attempt_dir), mode=mode, worker=worker)
            record["attempts"].append(attempt)
    except Exception as exc:
        record.update(error_type=type(exc).__name__, error=str(exc))
        print(f"{spec.alias}: {type(exc).__name__}: {exc}", flush=True)
    finally:
        if staging is not None:
            before = time.perf_counter()
            try:
                record["staging_peak_bytes"] = max(record.get("staging_peak_bytes", 0),
                                                   directory_size(staging))
                cleanup_staging(staging, parent, owner)
                record["staging_removed"] = True
            except Exception as exc:
                record.update(status="failed", cleanup_error=str(exc), staging_removed=False)
            record["cleanup_seconds"] = time.perf_counter() - before
        record["total_seconds"] = time.perf_counter() - started
    print(f"{spec.alias}: {record['status']} ({record['total_seconds']:.1f}s)", flush=True)
    return record


def main(argv=None, model_alias=None):
    args = parse_args(argv, model_alias=model_alias)
    if args.storage:
        for spec in args.selected:
            if spec.requires_prompt and spec.alias not in args.prompts:
                prompt = ROOT / "prompts/shared-zero-shot-v2.md"
                args.prompts[spec.alias] = {"prompt": prompt.read_text(), "prompt_file": str(prompt)}
    if args.list_models:
        for spec in MODELS:
            print(f"{spec.alias:24} {spec.repo} [{spec.precision}; {spec.language}; {spec.task}]")
        return 0
    if args.storage:
        args.storage = configure(args.storage)
        args.staging_dir = args.storage / "tmp"
        args.ram_staging_dir = args.storage / "tmp" / ".disabled-ram-fallback"
        args.output_dir = args.output_dir or args.storage / "results" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + uuid.uuid4().hex[:8])
    if args.remote_storage:
        root = args.remote_storage.expanduser().absolute()
        check = subprocess.run(['findmnt', '-n', '-o', 'FSTYPE,TARGET,SOURCE', '--mountpoint', str(root)], capture_output=True, text=True)
        fields = check.stdout.strip().split()
        if check.returncode or len(fields) != 3 or fields[0] != 'fuse.sshfs' or fields[2] != 'marcele_araponga@150.164.2.42:/home/marcele_araponga/phd-models':
            raise RuntimeError(f'Expected Greenwich SSHFS mount at {root}; refusing local fallback')
        args.remote_storage = root
        for directory in ('tmp', 'checkpoints', 'results', 'venv', 'cache/uv', 'cache/xdg', 'cache/torch', 'cache/triton', 'cache/cuda', 'cache/pip', 'huggingface', 'cache/nltk'):
            (root / directory).mkdir(parents=True, exist_ok=True)
        for key, path in {'UV_CACHE_DIR':'cache/uv', 'XDG_CACHE_HOME':'cache/xdg', 'TORCH_HOME':'cache/torch', 'TRITON_CACHE_DIR':'cache/triton', 'CUDA_CACHE_PATH':'cache/cuda', 'PIP_CACHE_DIR':'cache/pip', 'TMPDIR':'tmp', 'CLAIM_CHECKPOINT_CACHE':'checkpoints', 'CLAIM_NLTK_DIR':'cache/nltk'}.items():
            os.environ[key] = str(root / path)
        tempfile.tempdir = str(root / 'tmp')
        args.staging_dir = root / 'tmp'
        args.ram_staging_dir = root / 'tmp' / '.disabled-ram-fallback'
        args.output_dir = args.output_dir or root / 'results'
        if not args.output_dir.resolve().is_relative_to(root.resolve()):
            raise RuntimeError('Remote profile requires output directory on the SSHFS mount')
    if not shutil.which("uv"):
        raise RuntimeError("uv is not installed")
    if platform.system() != "Linux":
        raise RuntimeError("Run this script inside the Linux SSH server session")
    def interrupt(_signum, _frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupt)
    # Must be set before huggingface_hub's first import.
    os.environ["HF_HUB_DISABLE_XET"] = "1"
    inputs, aps = prepare_inputs(args)
    if args.output_dir is not None:
        args.output_dir.mkdir(parents=True, exist_ok=True)
    if args.storage and not args.check:
        if any(args.output_dir.iterdir()):
            raise RuntimeError("Results directory is not empty; choose a fresh --output-dir")
        write_json(args.output_dir / "inputs.json", inputs)
    args.staging_dir.mkdir(parents=True, exist_ok=True)
    records = []
    # Worker communication and runtime probes live only in this temporary directory.
    with tempfile.TemporaryDirectory(prefix="claim-run-", dir=args.staging_dir) as temporary:
        run_dir = Path(temporary)
        runtimes = {}
        if args.check:
            failures = []
            for spec in args.selected:
                try:
                    state = ensure_runtime(args, spec, run_dir, runtimes)
                    mode = spec.precision if args.precision == "auto" else args.precision
                    if mode == "nf4" and not ensure_quantization(args, spec, state):
                        failures.append(f"{spec.alias}: NF4 probe failed; offload would be used")
                except Exception as exc:
                    failures.append(f"{spec.alias}: {exc}")
            print("\n".join(failures) if failures else "All selected runtime/CUDA checks passed.", flush=True)
            return int(bool(failures))
        for spec in args.selected:
            destination = (args.output_dir or Path(spec.default_output)).resolve() / spec.alias
            if destination.exists() and any(destination.iterdir()):
                raise RuntimeError(f"Results already exist in {destination}. Use another --output-dir to keep both runs.")
            destination.mkdir(parents=True, exist_ok=True)
            model_args = copy.copy(args)
            if args.storage and spec.alias == "babelscape-t5" and args.context_tokens is None:
                model_args.context_tokens = 512
            record = run_one(model_args, spec, run_dir, inputs, aps, runtimes)
            export_result(record, destination)
            records.append(record)
            if args.storage:
                summary = [{"alias": item["alias"], **json.loads(
                    (args.output_dir / item["alias"] / "processing.json").read_text())}
                    for item in records]
                write_json(args.output_dir / "summary.json", summary)
            print(f"Output and processing: {destination}", flush=True)
            if record["status"] == "interrupted" or record.get("cleanup_error"):
                break
    if any(r["status"] == "interrupted" for r in records):
        return 130
    return int(len(records) != len(args.selected) or any(r["status"] != "success" for r in records))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Interrupted; worker stopped and owned staging cleaned.", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
