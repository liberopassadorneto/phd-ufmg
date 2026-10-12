"""Write the model's native output and one readable JSON resource report."""

import json
from pathlib import Path

from .resources import GIB, write_json


def extension(adapter):
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
    cpu = [(r["process_cpu_percent_mean"], r.get("sample_count", 1))
           for r in samples if r.get("process_cpu_percent_mean") is not None]
    cpu_mean = sum(value * count for value, count in cpu) / sum(count for _, count in cpu) if cpu else None
    last = workers[-1] if workers else {}
    result = {
        "model": record["model"]["repo"],
        "status": record["status"],
        "precision": attempts[-1]["mode"] if attempts else None,
        "gpu": last.get("gpu"),
        "inference_seconds": round(sum(w.get("inference_seconds", 0) for w in workers), 3) if workers else None,
        "loading_seconds": round(sum(w.get("load_seconds", 0) for w in workers), 3) if workers else None,
        "download_seconds": round(record.get("download_seconds", 0), 3),
        "total_seconds": round(record.get("total_seconds", 0), 3),
        "vram_peak_gib": gib(nvml if valid_nvml else torch_peak),
        "vram_measurement": "NVML process memory" if valid_nvml else "PyTorch allocated memory",
        "ram_peak_gib": gib(peak(workers, ["process_max_rss_bytes"])),
        "cpu_average_percent": round(cpu_mean, 2) if cpu_mean is not None else None,
        "cpu_peak_percent": peak(samples, ["process_cpu_percent_peak"]),
        "cpu_seconds": round(sum(w.get("process_cpu_seconds", 0) for w in workers), 3) if workers else None,
        "temporary_storage_peak_gib": gib(record.get("staging_peak_bytes")),
        "temporary_storage_location": record.get("staging_kind"),
        "temporary_weights_removed": record.get("staging_removed"),
        "output_bytes": sum(path.stat().st_size for path in files),
    }
    if last.get("truncated_chunks"):
        result["warning"] = "Model output reached the generation limit and is incomplete; preserved without repair."
    if last.get("generation_policy"):
        result["generation_policy"] = last["generation_policy"]
    if last.get("output_issues"):
        result["output_issues"] = last["output_issues"]
        result["warning"] = "Model output violates the card guarantees; preserved without repair."
        if last.get("truncated_chunks"):
            result["warning"] += " Generation also reached the token limit."
    errors = [{"precision": attempt["mode"],
               "phase": worker.get("failure_phase"), "type": worker.get("error_type"),
               "error": worker["error"], "traceback": worker.get("error_traceback")}
              for attempt, worker in zip(attempts, workers) if worker.get("error")]
    if errors:
        result["attempt_errors"] = errors
    if extension(record["model"]["adapter"]) == ".json":
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
    write_json(destination / "processing.json", processing(record, files))
