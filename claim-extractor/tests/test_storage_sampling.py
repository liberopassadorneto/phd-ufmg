import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from claim_runner.resources import Monitor


class StorageSamplingTests(unittest.TestCase):
    def test_running_means_discard_observations_and_ignore_missing_values(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict('sys.modules', {'pynvml': None}):
            monitor = Monitor(Path(tmp) / 'samples.jsonl')
            for cpu, ram, vram in [(None, 0, None), (100, 10, 20), (300, 30, 40)]:
                row = monitor._sample()
                row.update(process_cpu_percent=cpu, process_cpu_seconds=1 if cpu is not None else None,
                           process_rss_bytes=ram, gpu_process_vram_bytes=vram)
                monitor._record(row)
            self.assertEqual(monitor.summary['process_cpu_percent_mean'], 200)
            self.assertEqual(monitor.summary['process_rss_mean_bytes'], 20)
            self.assertEqual(monitor.summary['gpu_process_vram_mean_bytes'], 30)
            self.assertEqual(monitor.summary['process_rss_samples'], 2)
            self.assertEqual(monitor.summary['gpu_process_vram_peak_bytes'], 40)
            self.assertFalse(hasattr(monitor, 'cpu_samples'))
            self.assertFalse(monitor.output.exists())

    def test_storage_only_at_boundaries_while_resources_sample_every_tick(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict('sys.modules', {'pynvml': None}):
            root = Path(tmp)
            monitor = Monitor(root / 'samples.jsonl', staging=root)
            with patch.object(monitor.stop_event, 'wait', side_effect=[False, False, True]), \
                 patch('claim_runner.resources.directory_size', side_effect=[10, 30]) as size, \
                 patch('claim_runner.resources.shutil.disk_usage', side_effect=[SimpleNamespace(free=100), SimpleNamespace(free=80)]) as disk, \
                 patch.object(monitor.psutil, 'virtual_memory', wraps=monitor.psutil.virtual_memory) as ram:
                monitor._loop()
            self.assertEqual(size.call_count, 2)
            self.assertEqual(disk.call_count, 2)
            self.assertEqual(ram.call_count, 4)
            self.assertEqual(monitor.summary['sample_count'], 4)
            self.assertEqual(monitor.summary['staging_peak_bytes'], 30)
            self.assertEqual(monitor.summary['filesystem_free_min_bytes'], 80)
            self.assertEqual(monitor.summary['storage_sampling'], 'start_and_end')

    def test_normal_sample_does_not_walk_or_query_storage(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict('sys.modules', {'pynvml': None}):
            monitor = Monitor(Path(tmp) / 'samples.jsonl', staging=Path(tmp))
            with patch('claim_runner.resources.directory_size') as size, \
                 patch('claim_runner.resources.shutil.disk_usage') as disk:
                row = monitor._sample()
                monitor._record(row)
            size.assert_not_called()
            disk.assert_not_called()
            self.assertIsNone(row['staging_bytes'])
            self.assertIn('system_cpu_percent', row)
            self.assertIn('gpu_process_vram_bytes', row)


if __name__ == '__main__':
    unittest.main()
