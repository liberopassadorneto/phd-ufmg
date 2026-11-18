import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from claim_runner.storage import configure, runtime_identity, runtime_stamp, verify_runtime
from claim_runner.catalog import select_models
import run_models


class LocalTests(unittest.TestCase):
    def test_all_skips_newsscope_but_explicit_selection_remains(self):
        self.assertNotIn('newsscope', [spec.alias for spec in select_models('all')])
        self.assertFalse(select_models('newsscope')[0].hardware_configuration['offload_fallback'])

    def test_storage_preserves_huggingface_login_location(self):
        for configured_home in (None, '/custom/huggingface'):
            with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ):
                old_temp = tempfile.tempdir
                try:
                    os.environ['XDG_CACHE_HOME'] = '/original/cache'
                    os.environ['HF_TOKEN_PATH'] = '/custom/token'
                    os.environ.pop('HF_HOME', None)
                    if configured_home:
                        os.environ['HF_HOME'] = configured_home
                    configure(Path(tmp) / 'storage')
                    self.assertEqual(os.environ['HF_HOME'], configured_home or '/original/cache/huggingface')
                    self.assertEqual(os.environ['HF_TOKEN_PATH'], '/custom/token')
                finally:
                    tempfile.tempdir = old_temp

    def test_runtime_integrity_and_storage(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ):
            old_temp = tempfile.tempdir
            try:
                root = configure(Path(tmp) / 'storage')
                self.assertEqual(os.environ['UV_CACHE_DIR'], str(root / 'cache/uv'))
                project = Path(tmp) / 'project'
                project.mkdir()
                for name in ('pyproject.toml', 'uv.lock'):
                    (project / name).write_text('first')
                spec = SimpleNamespace(alias='test', runtime='test')
                with self.assertRaises(RuntimeError):
                    verify_runtime(root, spec, project, '3.10')
                (root / 'venv/test/bin').mkdir(parents=True)
                (root / 'venv/test/bin/python').symlink_to('/usr/bin/python3')
                runtime_stamp(root, spec).write_text(json.dumps(runtime_identity(project, '3.10')))
                verify_runtime(root, spec, project, '3.10')
                (project / 'uv.lock').write_text('changed')
                with self.assertRaises(RuntimeError):
                    verify_runtime(root, spec, project, '3.10')
            finally:
                tempfile.tempdir = old_temp

    def test_offline_requires_storage_and_conflicting_profiles(self):
        for argv in (['--offline'], ['--storage', '/tmp/a', '--remote-storage', '/tmp/b']):
            with self.assertRaises(SystemExit):
                run_models.parse_args(argv)

    def test_offline_runtime_skips_sync(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = select_models('babelscape-t5')[0]
            args = run_models.parse_args(['--models', spec.alias, '--storage', tmp, '--offline'])
            with patch.object(run_models, 'verify_runtime'), patch.object(run_models, 'command_record', return_value={'returncode': 0}) as command:
                state = run_models.ensure_runtime(args, spec, Path(tmp), {})
            self.assertTrue(state['setup']['prepared'])
            command.assert_not_called()

    def test_explicit_check_runs_cuda_and_nf4_probes(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = select_models('principled-4b')[0]
            args = run_models.parse_args(['--models', spec.alias, '--storage', tmp, '--offline', '--check'])
            with patch.object(run_models, 'verify_runtime') as verify, patch.object(run_models, 'command_record', return_value={'returncode': 0}) as command:
                state = run_models.ensure_runtime(args, spec, Path(tmp), {})
                self.assertTrue(run_models.ensure_quantization(args, spec, state))
            verify.assert_called_once()
            self.assertEqual(command.call_count, 2)
            self.assertTrue(all('--probe' in call.args[0] for call in command.call_args_list))
            self.assertIn('--quantized', command.call_args.args[0])

    def test_check_command_passes_runtime_state_to_quantization(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ):
            old_temp = tempfile.tempdir
            try:
                with patch.object(run_models, 'ensure_runtime', return_value={'cuda': {'returncode': 0}}) as runtime, patch.object(run_models, 'ensure_quantization', return_value=True) as quantization:
                    result = run_models.main(['--check', '--storage', tmp, '--offline', '--models', 'principled-4b'])
                self.assertEqual(result, 0)
                self.assertEqual(quantization.call_args.args[2], runtime.return_value)
            finally:
                tempfile.tempdir = old_temp



if __name__ == '__main__':
    unittest.main()

class MetricsTests(unittest.TestCase):
    def test_metrics_and_attempt_artifacts_persist(self):
        from claim_runner.outputs import export_result
        from claim_runner.resources import GIB
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'attempt'
            source.mkdir()
            for name, value in [('output.raw', 'native output'), ('process.log', 'log'),
                                ('resource-samples.jsonl', '{"elapsed_seconds":1}\n')]:
                (source / name).write_text(value)
            record = {'model': {'repo': 'test/model', 'output_format': '.raw'}, 'status': 'success',
                      'cpu_threads': 8, 'attempts': [{'directory': str(source), 'mode': 'fp16',
                      'worker': {'process_max_rss_bytes': GIB, 'inference_seconds': 2},
                      'resources': {'process_rss_peak_bytes': 2 * GIB, 'process_cpu_percent_mean': 250,
                                    'process_cpu_percent_peak': 400, 'sample_count': 2,
                                    'process_rss_mean_bytes': 1.5 * GIB, 'process_rss_samples': 2,
                                    'gpu_process_vram_mean_bytes': 2 * GIB, 'gpu_process_vram_samples': 2,
                                    'gpu_process_vram_peak_bytes': 3 * GIB}}]}
            target = Path(tmp) / 'result'
            export_result(record, target)
            data = json.loads((target / 'processing.json').read_text())
            self.assertEqual(data['vcpu_average_used'], 2.5)
            self.assertEqual(data['vcpu_peak_used'], 4)
            self.assertEqual(data['ram_peak_gib'], 2)
            self.assertEqual(data['vram_peak_gib'], 3)
            self.assertEqual(data['ram_average_gib'], 1.5)
            self.assertEqual(data['vram_average_gib'], 2)
            self.assertFalse(data['individual_resource_samples_saved'])
            self.assertEqual(data['cpu_threads_configured'], 8)
            self.assertEqual((target / 'output.raw').read_text(), 'native output')
            self.assertFalse((target / 'attempt-1-fp16/resource-samples.jsonl').exists())
            self.assertEqual((target / 'attempt-1-fp16/process.log').read_text(), 'log')
