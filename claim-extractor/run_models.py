#!/usr/bin/env python3
"""Run the claim-extractor checkpoint catalog sequentially on the CUDA server."""

from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import time
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path

from claim_runner.catalog import MODELS, select_models
from claim_runner.downloads import download_repositories, repository_manifest
from claim_runner.inputs import make_aps, read_aps, read_transcript
from claim_runner.resources import (GIB, Monitor, choose_staging, cleanup_staging,
                                    create_staging, directory_size, write_json)

ROOT = Path(__file__).resolve().parent


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", default="all", help="Comma-separated aliases/HF IDs or all")
    parser.add_argument("--list-models", action="store_true")
    parser.add_argument("--check", action="store_true", help="Install/check runtimes and CUDA; do not download models")
    parser.add_argument("--input-en", type=Path, default=ROOT / "automatic.en.txt")
    parser.add_argument("--input-pt", type=Path, default=ROOT / "automatic.srt")
    parser.add_argument("--aps-input", type=Path, help="Frozen APS JSONL; defaults to bundled file for bundled English text")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results")
    parser.add_argument("--staging-dir", type=Path, default=ROOT / ".model-staging")
    parser.add_argument("--ram-staging-dir", type=Path, default=Path("/dev/shm"))
    parser.add_argument("--runtime-dir", type=Path, default=ROOT / "runtimes")
    parser.add_argument("--python", default="3.10", help="Python version used by uv worker runtimes")
    parser.add_argument("--precision", choices=("auto", "fp16", "fp32", "nf4", "offload"), default="auto")
    parser.add_argument("--no-offload-fallback", action="store_true")
    parser.add_argument("--disk-reserve-gib", type=float, default=5)
    parser.add_argument("--ram-reserve-gib", type=float, default=8)
    parser.add_argument("--gpu-reserve-gib", type=float, default=1)
    parser.add_argument("--context-tokens", type=int, default=8192,
                        help="Upper bound for input + output context (default 8192)")
    parser.add_argument("--max-new-tokens", type=int, help="Override model-specific output limit")
    parser.add_argument("--cpu-threads", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--model-timeout", type=float, default=0,
                        help="Seconds per worker attempt; 0 disables timeout")
    args = parser.parse_args(argv)
    for name in ("disk_reserve_gib", "ram_reserve_gib", "gpu_reserve_gib", "model_timeout"):
        if getattr(args, name) < 0:
            parser.error(f"--{name.replace('_', '-')} must be nonnegative")
    if args.context_tokens < 1 or args.cpu_threads < 1 or (
            args.max_new_tokens is not None and args.max_new_tokens < 1):
        parser.error("Token limits and CPU threads must be positive")
    try:
        args.selected = select_models(args.models)
    except ValueError as exc:
        parser.error(str(exc))
    for spec in args.selected:
        maximum = args.max_new_tokens or spec.max_new_tokens
        if spec.adapter not in ("t5", "fc_t5", "claimpt") and maximum >= args.context_tokens:
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
            "python", "-m", "claim_runner.worker", *map(str, extra)]


def ensure_runtime(args, spec, run_dir, cache):
    if spec.runtime not in cache:
        folder = run_dir / "preflight" / spec.runtime
        project = args.runtime_dir / spec.runtime
        if not (project / "uv.lock").is_file():
            raise RuntimeError(f"Missing runtime lock: {project / 'uv.lock'}")
        additional_budget = 0 if (project / ".venv" / "pyvenv.cfg").is_file() else 4 * GIB
        if shutil.disk_usage(project).free < args.disk_reserve_gib * GIB + additional_budget:
            raise RuntimeError("Insufficient disk for uv runtime setup plus reserve; relocate --runtime-dir")
        print(f"Preparing uv runtime: {spec.runtime}", flush=True)
        setup = command_record(["uv", "sync", "--frozen", "--project", str(project.resolve()),
                                "--python", args.python], folder / "setup")
        if setup["returncode"] != 0:
            raise RuntimeError(f"Runtime setup failed; see {folder / 'setup/process.log'}")
        probe_dir = folder / "cuda"
        probe_dir.mkdir(parents=True, exist_ok=True)
        cuda = command_record(worker_command(args, spec, "--probe", probe_dir / "cuda.json"),
                              probe_dir, timeout=120)
        cache[spec.runtime] = {"setup": setup, "cuda": cuda, "folder": str(folder)}
    state = cache[spec.runtime]
    if state["cuda"]["returncode"] != 0:
        raise RuntimeError(f"CUDA/FP16 preflight failed; see {state['folder']}/cuda/process.log")
    return state


def ensure_quantization(args, spec, state):
    if "nf4" not in state:
        folder = Path(state["folder"]) / "nf4"
        folder.mkdir(parents=True, exist_ok=True)
        state["nf4"] = command_record(worker_command(args, spec, "--probe", folder / "nf4.json", "--quantized"),
                                      folder, timeout=120)
    return state["nf4"]["returncode"] == 0


def prepare_inputs(args):
    inputs = {}
    if any(spec.language == "en" for spec in args.selected):
        inputs["en"] = read_transcript(args.input_en)
    if any(spec.language == "pt" for spec in args.selected):
        inputs["pt"] = read_transcript(args.input_pt)
    aps = None
    if any(spec.adapter == "aps" for spec in args.selected):
        frozen = args.aps_input
        if frozen is None and args.input_en.resolve() == (ROOT / "automatic.en.txt").resolve():
            frozen = ROOT / "automatic.en.aps-input.jsonl"
        aps = read_aps(frozen, inputs["en"]["text"]) if frozen else make_aps(
            inputs["en"]["text"], ROOT / ".runner-nltk")
    return inputs, aps


def run_one(args, spec, run_dir, inputs, aps, runtimes):
    output = run_dir / spec.alias
    output.mkdir()
    started = time.perf_counter()
    owner = uuid.uuid4().hex
    staging = parent = None
    record = {"alias": spec.alias, "model": spec.record(), "status": "failed", "attempts": [],
              "download_seconds": 0.0, "cleanup_seconds": 0.0,
              "started_at": datetime.now(timezone.utc).isoformat()}
    write_json(output / "input.json", {"source": inputs[spec.language], "aps": aps if spec.adapter == "aps" else None})
    write_json(output / "model-card.json", spec.record())
    try:
        preflight_started = time.perf_counter()
        state = ensure_runtime(args, spec, run_dir, runtimes)
        mode = spec.precision if args.precision == "auto" else args.precision
        if spec.adapter in ("t5", "fc_t5", "claimpt") and mode == "nf4":
            raise ValueError("NF4 override is supported only for the causal language models")
        if mode == "nf4" and not ensure_quantization(args, spec, state):
            record["quantization_preflight_failed"] = True
            if args.no_offload_fallback:
                raise RuntimeError("NF4 CUDA probe failed and offload fallback is disabled")
            mode = "offload"
        record["preflight_seconds"] = time.perf_counter() - preflight_started
        manifests = [repository_manifest(spec.repo, spec.revision)]
        if spec.base_repo:
            manifests.append(repository_manifest(spec.base_repo))
        write_json(output / "download-manifest.json", manifests)
        download_bytes = sum(m["download_bytes"] for m in manifests)
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
            repositories = download_repositories(manifests, staging)
        finally:
            record["download_seconds"] = time.perf_counter() - before
            record["download_resources"] = monitor.stop()
        record["staging_peak_bytes"] = directory_size(staging)
        for index, repository in enumerate(repositories):
            source_dir = output / f"upstream-{index}"
            source_dir.mkdir()
            for filename in ("README.md", "config.json", "generation_config.json",
                             "adapter_config.json", "prompt.txt", "schema.json"):
                path = Path(repository["local_path"]) / filename
                if path.is_file():
                    shutil.copyfile(path, source_dir / filename)
        # Exact dependency locks and resolved checkpoint SHAs survive staging deletion.
        for project in (ROOT / "pyproject.toml", ROOT / "uv.lock",
                        args.runtime_dir / spec.runtime / "pyproject.toml",
                        args.runtime_dir / spec.runtime / "uv.lock"):
            if project.exists():
                shutil.copyfile(project, output / f"{project.parent.name}-{project.name}")
        environment = os.environ.copy()
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
                "input": inputs[spec.language], "aps": aps, "output": str(attempt_dir.resolve()),
                "seed": args.seed, "cpu_threads": args.cpu_threads,
                "gpu_reserve_bytes": int(args.gpu_reserve_gib * GIB),
                "context_tokens": args.context_tokens, "max_new_tokens": args.max_new_tokens})
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
            if attempt.get("timed_out") or args.no_offload_fallback or mode in ("offload", "fp32") or not retry:
                break
            print(f"{spec.alias}: retrying with RAM weight offload; first attempt preserved", flush=True)
            mode = "offload"
        record["load_seconds"] = sum(a["worker"].get("load_seconds", 0) for a in record["attempts"])
        record["inference_seconds"] = sum(a["worker"].get("inference_seconds", 0) for a in record["attempts"])
    except KeyboardInterrupt:
        record.update(status="interrupted", error="Interrupted by signal or keyboard")
    except Exception as exc:
        record.update(error_type=type(exc).__name__, error=str(exc))
        (output / "supervisor-error.log").write_text(traceback.format_exc(), encoding="utf-8")
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
        record["artifacts_bytes"] = directory_size(output)
        write_json(output / "result.json", record)
    print(f"{spec.alias}: {record['status']} ({record['total_seconds']:.1f}s)", flush=True)
    return record


def hardware_record():
    import psutil
    record = {"hostname": platform.node(), "platform": platform.platform(),
              "logical_cpus": psutil.cpu_count(), "physical_cpus": psutil.cpu_count(logical=False),
              "ram_total_bytes": psutil.virtual_memory().total,
              "ram_available_bytes": psutil.virtual_memory().available,
              "swap_total_bytes": psutil.swap_memory().total}
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        lines = cpuinfo.read_text().splitlines()
        record["cpu_model"] = next((line.split(":", 1)[1].strip() for line in lines
                                    if line.startswith("model name")), None)
        record["cpu_flags"] = next((line.split(":", 1)[1].split() for line in lines
                                    if line.startswith("flags")), [])
    if shutil.which("nvidia-smi"):
        try:
            query = subprocess.run(["nvidia-smi", "--query-gpu=name,driver_version,memory.total,memory.free",
                                    "--format=csv,noheader"], capture_output=True, text=True, timeout=15)
            record["nvidia_smi"] = query.stdout.strip() if query.returncode == 0 else query.stderr.strip()
        except subprocess.TimeoutExpired:
            record["nvidia_smi"] = "Timed out"
    return record


def save_summary(run_dir, records, metadata):
    write_json(run_dir / "summary.json", {**metadata, "models": records})
    rows = []
    for record in records:
        samples = [a["resources"] for a in record["attempts"]]
        workers = [a["worker"] for a in record["attempts"]]
        def peak(key):
            values = [s[key] for s in samples if s.get(key) is not None]
            return max(values) if values else None
        def worker_peak(*keys):
            values = [w[key] for w in workers for key in keys if w.get(key) is not None]
            return max(values) if values else None
        rows.append({"model": record["alias"], "status": record["status"],
                     "modes": ",".join(a["mode"] for a in record["attempts"]),
                     "download_seconds": record["download_seconds"],
                     "preflight_seconds": record.get("preflight_seconds"),
                     "load_seconds": record.get("load_seconds"),
                     "inference_seconds": record.get("inference_seconds"),
                     "cleanup_seconds": record["cleanup_seconds"], "total_seconds": record["total_seconds"],
                     "vram_process_peak_bytes": peak("gpu_process_vram_peak_bytes"),
                     "vram_device_peak_bytes": peak("gpu_device_vram_peak_bytes"),
                     "torch_allocated_peak_bytes": worker_peak("torch_load_peak_allocated_bytes",
                                                                "torch_inference_peak_allocated_bytes",
                                                                "torch_failure_peak_allocated_bytes"),
                     "ram_process_peak_bytes": worker_peak("process_max_rss_bytes"),
                     "ram_system_peak_bytes": peak("system_ram_used_peak_bytes"),
                     "cpu_percent_peak": peak("process_cpu_percent_peak"),
                     "cpu_seconds": sum(w.get("process_cpu_seconds", 0) for w in workers) if workers else None,
                     "staging_peak_bytes": record.get("staging_peak_bytes"),
                     "artifacts_bytes": record["artifacts_bytes"],
                     "error": record.get("error") or next((w.get("error") for w in reversed(workers)
                                                         if w.get("error")), None)})
    if rows:
        with (run_dir / "summary.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)


def main(argv=None):
    args = parse_args(argv)
    if args.list_models:
        for spec in MODELS:
            print(f"{spec.alias:24} {spec.repo} [{spec.precision}; {spec.language}; {spec.task}]")
        return 0
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
    args.output_dir.mkdir(parents=True, exist_ok=True)
    run_dir = args.output_dir.resolve() / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                                          + "-" + uuid.uuid4().hex[:8])
    run_dir.mkdir()
    metadata = {"schema_version": "1.0", "run_directory": str(run_dir), "hardware": hardware_record(),
                "input": inputs, "aps": aps, "started_at": datetime.now(timezone.utc).isoformat(),
                "selected_models": [spec.alias for spec in args.selected]}
    write_json(run_dir / "run.json", metadata)
    print(f"Results: {run_dir}", flush=True)
    runtimes = {}
    records = []
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
        write_json(run_dir / "check.json", {"runtimes": runtimes, "failures": failures})
        print("\n".join(failures) if failures else "All selected runtime/CUDA checks passed.", flush=True)
        return int(bool(failures))
    try:
        for spec in args.selected:
            record = run_one(args, spec, run_dir, inputs, aps, runtimes)
            records.append(record)
            save_summary(run_dir, records, metadata)
            if record["status"] == "interrupted":
                break
            if record.get("cleanup_error"):
                print("Stopping: staging cleanup failed; no next model will be downloaded.", flush=True)
                break
    finally:
        metadata["finished_at"] = datetime.now(timezone.utc).isoformat()
        save_summary(run_dir, records, metadata)
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
