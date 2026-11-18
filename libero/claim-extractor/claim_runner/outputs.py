"""Write the model's native output and one readable JSON resource report."""

import json
import os
import shutil
from pathlib import Path

from .resources import GIB, write_json


def extension(adapter):
    if adapter in (".raw", ".json"):
        return adapter
    return ".raw" if adapter in ("aps", "t5", "fc_t5") else ".json"


def write_outputs(destination: Path, adapter: str, blocks: list[str], chunk_count=None) -> list[Path]:
    destination.mkdir(parents=True, exist_ok=True)
    suffix = extension(adapter)
    if suffix == ".raw" or (chunk_count or len(blocks)) <= 1:
        path = destination / ("output" + suffix)
        path.write_text("\n\n".join(blocks), encoding="utf-8")
        return [path]
    # Each JSON response is kept intact; do not merge or repair model objects.
    paths = []
    for index, block in enumerate(blocks, 1):
        path = destination / f"output-{index:03d}{suffix}"
        path.write_text(block, encoding="utf-8")
        paths.append(path)
    return paths


def processing(record: dict, files: list[Path]) -> dict:
    attempts = record.get("attempts", [])
    workers = [a.get("worker", {}) for a in attempts]
    samples = [a.get("resources", {}) for a in attempts]

    def peak(records, keys):
        values = [r[k] for r in records for k in keys if r.get(k) is not None]
        return max(values) if values else None

    def gib(value):
        return round(value / GIB, 3) if value is not None else None

    nvml = peak(samples, ["gpu_process_vram_peak_bytes"])
    torch_peak = peak(workers, ["torch_load_peak_allocated_bytes",
                               "torch_inference_peak_allocated_bytes",
                               "torch_failure_peak_allocated_bytes"])
    valid_nvml = nvml is not None and nvml > 0
    def average(field, count_field):
        values = [(r[field], r.get(count_field, r.get("sample_count", 1)))
                  for r in samples if r.get(field) is not None]
        count = sum(n for _, n in values)
        return sum(value * n for value, n in values) / count if count else None

    cpu_mean = average("process_cpu_percent_mean", "process_cpu_percent_samples")
    last = workers[-1] if workers else {}
    result = {
        "model": record["model"]["repo"],
        "status": record["status"],
        "precision": attempts[-1]["mode"] if attempts else None,
        "gpu": last.get("gpu"),
        "inference_seconds": round(sum(w.get("inference_seconds", 0) for w in workers), 3) if workers else None,
        "loading_seconds": round(sum(w.get("load_seconds", 0) for w in workers), 3) if workers else None,
        "preflight_seconds": round(record.get("preflight_seconds", 0), 3),
        "checkpoint_verification_seconds": round(record["checkpoint_verification_seconds"], 3) if "checkpoint_verification_seconds" in record else None,
        "download_seconds": round(record.get("download_seconds", 0), 3),
        "total_seconds": round(record.get("total_seconds", 0), 3),
        "vram_average_gib": gib(average("gpu_process_vram_mean_bytes", "gpu_process_vram_samples")),
        "vram_average_measurement": "NVML process memory; null when unavailable",
        "ram_average_gib": gib(average("process_rss_mean_bytes", "process_rss_samples")),
        "averaging_method": "Mean of valid one-second observations across worker attempts, including loading and inference; not energy consumption",
        "individual_resource_samples_saved": False,
        "vram_peak_gib": gib(nvml if valid_nvml else torch_peak),
        "vram_measurement": "NVML process memory" if valid_nvml else "PyTorch allocated memory",
        "ram_peak_gib": gib(peak(workers, ["process_max_rss_bytes"]) if not samples else
                            max(peak(workers, ["process_max_rss_bytes"]) or 0,
                                peak(samples, ["process_rss_peak_bytes"]) or 0)),
        "cpu_logical_count": os.cpu_count(),
        "cpu_available_logical_count": len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else os.cpu_count(),
        "cpu_threads_configured": record.get("cpu_threads"),
        "vcpu_average_used": round(cpu_mean / 100, 3) if cpu_mean is not None else None,
        "vcpu_peak_used": round(peak(samples, ["process_cpu_percent_peak"]) / 100, 3)
                         if peak(samples, ["process_cpu_percent_peak"]) is not None else None,
        "resource_sampling_interval_seconds": 1,
        "resource_measurement_notes": "CPU 100% = one logical CPU; vCPU usage is CPU percent / 100. "
                                      "RAM includes the sampled process tree; brief peaks may be missed.",
        "resource_measurement_unavailable": sorted({reason for sample in samples for reason in sample.get("unavailable", [])}),
        "cpu_average_percent": round(cpu_mean, 2) if cpu_mean is not None else None,
        "cpu_peak_percent": peak(samples, ["process_cpu_percent_peak"]),
        "cpu_seconds": round(sum(w.get("process_cpu_seconds", 0) for w in workers), 3) if workers else None,
        "temporary_storage_peak_gib": gib(record.get("staging_peak_bytes")),
        "temporary_storage_measurement": "Maximum of start/end measurements; intermediate peaks are not sampled",
        "temporary_storage_location": record.get("staging_kind"),
        "persistent_checkpoints": record.get("persistent_checkpoints", False),
        "temporary_weights_removed": record.get("staging_removed"),
        "output_bytes": sum(path.stat().st_size for path in files),
    }
    if last.get("truncated_chunks"):
        result["warning"] = "Model output reached the generation limit and is incomplete; preserved without repair."
    configuration = last.get("configuration") or record.get("configuration")
    if configuration:
        result["configuration"] = configuration
    errors = [{"precision": attempt["mode"],
               "phase": worker.get("failure_phase"), "type": worker.get("error_type"),
               "error": worker["error"], "traceback": worker.get("error_traceback")}
              for attempt, worker in zip(attempts, workers) if worker.get("error")]
    if errors:
        result["attempt_errors"] = errors
    if extension(record["model"].get("output_format", record["model"].get("adapter"))) == ".json":
        try:
            for path in files:
                json.loads(path.read_text(encoding="utf-8"))
            result["output_valid_json"] = bool(files)
        except ValueError:
            result["output_valid_json"] = False
    error = record.get("error") or record.get("cleanup_error") or last.get("error")
    if last.get("max_new_tokens") is not None:
        result["max_new_tokens"] = last["max_new_tokens"]
    if last.get("context_tokens") is not None:
        result["context_tokens"] = last["context_tokens"]
    if last.get("chunks_expected") is not None:
        result["chunks_processed"] = last.get("chunks_completed", 0)
    if error:
        result["error"] = error
    return result


def export_result(record: dict, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    attempts = record.get("attempts", [])
    chosen = Path(record.get("selected_attempt") or attempts[-1]["directory"]) if attempts else None
    files = []
    if chosen is not None:
        for path in sorted(chosen.glob("output*")):
            if path.is_file() and path.suffix in (".raw", ".json"):
                target = destination / path.name
                target.write_bytes(path.read_bytes())
                files.append(target)
    # Preserve measurements and logs before the supervisor removes its temporary IPC directory.
    for index, attempt in enumerate(attempts, 1):
        source = Path(attempt["directory"])
        target = destination / f"attempt-{index}-{attempt['mode']}"
        target.mkdir(exist_ok=True)
        for name in ("process.log", "process-result.json", "worker-result.json"):
            if (source / name).is_file():
                shutil.copyfile(source / name, target / name)
    write_json(destination / "processing.json", processing(record, files))
