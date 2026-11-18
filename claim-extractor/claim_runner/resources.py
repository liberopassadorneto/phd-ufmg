"""Resource sampling without importing PyTorch into the supervisor process."""

import json
import os
import shutil
import tempfile
import threading
import time
from pathlib import Path

GIB = 1024 ** 3
OWNER_MARKER = ".claim-runner-owned"


def write_json(path: Path, record) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def directory_size(path: Path) -> int:
    """Count physical files once, including Hugging Face cache hardlinks."""
    total = 0
    seen = set()
    for root, dirs, files in os.walk(path, followlinks=False):
        dirs[:] = [name for name in dirs if not (Path(root) / name).is_symlink()]
        for name in files:
            try:
                stat = (Path(root) / name).stat()
                key = (stat.st_dev, stat.st_ino)
                if key not in seen:
                    total += stat.st_size
                    seen.add(key)
            except FileNotFoundError:
                pass
    return total


def create_staging(parent: Path, owner: str) -> Path:
    parent.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix="claim-model-", dir=parent))
    (path / OWNER_MARKER).write_text(owner, encoding="utf-8")
    return path


def cleanup_staging(path: Path, parent: Path, owner: str) -> None:
    """Refuse deletion of unowned paths, reused paths, and symlink replacements."""
    marker = path / OWNER_MARKER
    if (path.is_symlink() or path.resolve().parent != parent.resolve()
            or not path.name.startswith("claim-model-") or not marker.is_file()
            or marker.is_symlink() or marker.read_text(encoding="utf-8") != owner):
        raise RuntimeError(f"Refusing cleanup of non-owned staging: {path}")
    shutil.rmtree(path)


def choose_staging(download_bytes: int, memory_bytes: int, disk_parent: Path,
                   ram_parent: Path, disk_reserve: int, ram_reserve: int) -> tuple[Path, str]:
    import psutil
    available = psutil.virtual_memory().available
    if memory_bytes + ram_reserve > available:
        raise RuntimeError(f"Insufficient RAM: need {(memory_bytes + ram_reserve) / GIB:.2f} GiB, "
                           f"available {available / GIB:.2f} GiB")
    disk_parent.mkdir(parents=True, exist_ok=True)
    required = int(download_bytes * 1.05) + 64 * 1024 ** 2
    if required + disk_reserve <= shutil.disk_usage(disk_parent).free:
        return disk_parent, "disk"
    if (ram_parent.is_dir() and os.access(ram_parent, os.W_OK)
            and shutil.disk_usage(ram_parent).free >= required
            and available >= required + memory_bytes + ram_reserve):
        mounts = psutil.disk_partitions(all=True)
        candidates = [m for m in mounts if ram_parent.resolve().is_relative_to(Path(m.mountpoint))]
        mount = max(candidates, key=lambda m: len(m.mountpoint), default=None)
        if mount is not None and mount.fstype == "tmpfs":
            return ram_parent, "tmpfs"
    raise RuntimeError("Insufficient staging space in disk and tmpfs; use --staging-dir on a larger "
                       "filesystem or --ram-staging-dir pointing to an existing tmpfs. "
                       f"Checkpoint requires approximately {required / GIB:.2f} GiB before quantization.")


class Monitor:
    def __init__(self, output: Path, staging: Path | None = None, phase_path: Path | None = None):
        import psutil
        self.psutil = psutil
        self.output = output
        self.staging = staging
        self.phase_path = phase_path
        self.phase = "preflight"
        self.pid = None
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.known_processes = {}
        self.cpu_baseline = {}
        self.started = time.monotonic()
        self.summary = {"sampling_interval_seconds": 1, "storage_sampling": "start_and_end", "sample_count": 0,
                        "process_rss_peak_bytes": 0, "system_ram_used_peak_bytes": 0,
                        "system_ram_available_min_bytes": None, "system_swap_used_peak_bytes": 0,
                        "process_cpu_percent_peak": 0.0, "process_cpu_percent_mean": None,
                        "process_cpu_seconds": 0.0, "system_cpu_percent_peak": 0.0,
                        "gpu_process_vram_peak_bytes": None, "gpu_device_vram_peak_bytes": None,
                        "gpu_device_utilization_peak_percent": None, "staging_peak_bytes": 0,
                        "filesystem_free_min_bytes": None, "unavailable": []}
        # Running sums/counts only: individual observations are never retained.
        self.means = {"process_cpu_percent": [0.0, 0], "process_rss": [0.0, 0],
                      "gpu_process_vram": [0.0, 0]}
        self.nvml = None
        self.gpu = None
        try:
            import pynvml
            pynvml.nvmlInit()
            self.nvml = pynvml
            self.gpu = pynvml.nvmlDeviceGetHandleByIndex(0)
        except Exception as exc:
            self.summary["unavailable"].append(f"NVML: {type(exc).__name__}: {exc}")
        self.thread = threading.Thread(target=self._loop, daemon=True)

    def start(self):
        self.thread.start()
        return self

    def attach(self, pid):
        with self.lock:
            self.pid = pid
            self.known_processes = {}
            self.cpu_baseline = {}
            try:
                process = self.psutil.Process(pid)
                times = process.cpu_times()
                self.cpu_baseline[(pid, process.create_time())] = times.user + times.system
            except (self.psutil.NoSuchProcess, self.psutil.AccessDenied):
                pass

    def _sample(self, include_storage=False):
        psutil = self.psutil
        vm = psutil.virtual_memory()
        row = {"elapsed_seconds": time.monotonic() - self.started, "phase": self.phase,
               "system_ram_used_bytes": vm.total - vm.available,
               "system_ram_available_bytes": vm.available,
               "system_swap_used_bytes": psutil.swap_memory().used,
               "system_cpu_percent": psutil.cpu_percent(), "process_rss_bytes": 0,
               "process_cpu_percent": None, "process_cpu_seconds": None,
               "gpu_process_vram_bytes": None, "gpu_device_vram_bytes": None,
               "gpu_device_utilization_percent": None}
        if self.phase_path and self.phase_path.exists():
            try:
                row["phase"] = json.loads(self.phase_path.read_text())["phase"]
            except (OSError, ValueError, KeyError):
                pass
        pids = set()
        with self.lock:
            if self.pid:
                try:
                    processes = [psutil.Process(self.pid)]
                    processes += processes[0].children(recursive=True)
                    percent = 0.0
                    seconds = 0.0
                    for process in processes:
                        try:
                            key = (process.pid, process.create_time())
                            if key not in self.known_processes:
                                self.known_processes[key] = process
                            tracked = self.known_processes[key]
                            percent += tracked.cpu_percent()
                            times = tracked.cpu_times()
                            seconds += max(0, times.user + times.system - self.cpu_baseline.get(key, 0))
                            row["process_rss_bytes"] += tracked.memory_info().rss
                            pids.add(process.pid)
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            continue
                    row["process_cpu_percent"] = percent
                    row["process_cpu_seconds"] = seconds
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        if self.nvml:
            try:
                row["gpu_device_vram_bytes"] = self.nvml.nvmlDeviceGetMemoryInfo(self.gpu).used
                row["gpu_device_utilization_percent"] = self.nvml.nvmlDeviceGetUtilizationRates(self.gpu).gpu
                gpu_processes = self.nvml.nvmlDeviceGetComputeRunningProcesses(self.gpu)
                valid = [p.usedGpuMemory for p in gpu_processes if p.pid in pids]
                unavailable = getattr(self.nvml, "NVML_VALUE_NOT_AVAILABLE", 2 ** 64 - 1)
                if any(value is None or value == unavailable for value in valid):
                    row["gpu_process_vram_bytes"] = None
                elif pids:
                    row["gpu_process_vram_bytes"] = sum(valid)
            except Exception as exc:
                reason = f"NVML sample: {type(exc).__name__}: {exc}"
                if reason not in self.summary["unavailable"]:
                    self.summary["unavailable"].append(reason)
        row["staging_bytes"] = None
        row["filesystem_free_bytes"] = None
        if include_storage:
            row["staging_bytes"] = directory_size(self.staging) if self.staging else 0
            storage = self.staging if self.staging and self.staging.exists() else self.output.parent
            row["filesystem_free_bytes"] = shutil.disk_usage(storage).free
        return row

    def _record(self, row):
        s = self.summary
        s["sample_count"] += 1
        pairs = {"process_rss_peak_bytes": "process_rss_bytes",
                 "system_ram_used_peak_bytes": "system_ram_used_bytes",
                 "system_swap_used_peak_bytes": "system_swap_used_bytes",
                 "process_cpu_percent_peak": "process_cpu_percent",
                 "system_cpu_percent_peak": "system_cpu_percent",
                 "gpu_process_vram_peak_bytes": "gpu_process_vram_bytes",
                 "gpu_device_vram_peak_bytes": "gpu_device_vram_bytes",
                 "gpu_device_utilization_peak_percent": "gpu_device_utilization_percent",
                 "staging_peak_bytes": "staging_bytes"}
        for dest, source in pairs.items():
            if row[source] is not None:
                s[dest] = max(s[dest] or 0, row[source])
        for dest, source in (("system_ram_available_min_bytes", "system_ram_available_bytes"),
                             ("filesystem_free_min_bytes", "filesystem_free_bytes")):
            if row[source] is not None:
                s[dest] = row[source] if s[dest] is None else min(s[dest], row[source])
        observations = {"process_cpu_percent": row["process_cpu_percent"],
                        "process_rss": row["process_rss_bytes"] if row["process_cpu_seconds"] is not None else None,
                        "gpu_process_vram": row["gpu_process_vram_bytes"]}
        for name, value in observations.items():
            if value is not None:
                accumulator = self.means[name]
                accumulator[0] += value
                accumulator[1] += 1
                suffix = "_mean" if name == "process_cpu_percent" else "_mean_bytes"
                s[name + suffix] = accumulator[0] / accumulator[1]
                s[name + "_samples"] = accumulator[1]
        s["process_cpu_seconds"] = max(s["process_cpu_seconds"], row["process_cpu_seconds"] or 0)

    def _loop(self):
        first = True
        while True:
            try:
                self._record(self._sample(include_storage=first))
            except Exception as exc:
                reason = f"Resource sampling: {type(exc).__name__}: {exc}"
                if reason not in self.summary["unavailable"]:
                    self.summary["unavailable"].append(reason)
            first = False
            if self.stop_event.wait(1):
                try:
                    self._record(self._sample(include_storage=True))
                except Exception:
                    pass
                break

    def stop(self):
        self.stop_event.set()
        self.thread.join()
        if self.nvml:
            self.nvml.nvmlShutdown()
        if self.summary["process_cpu_percent_mean"] is None:
            self.summary["unavailable"].append("No live worker CPU samples were captured")
        return self.summary
