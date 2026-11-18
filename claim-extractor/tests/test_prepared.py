import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from claim_runner.prepared import publish, load


class PreparedTests(unittest.TestCase):
    def test_integrity_and_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = SimpleNamespace(alias='model', repo='org/model', revision='abc', base_repo=None)
            with self.assertRaises(RuntimeError):
                load(root, spec)
            folder = root / 'checkpoints' / 'item'
            folder.mkdir(parents=True)
            (folder / 'weights').write_bytes(b'test')
            publish(root, 'model', [{'repo': 'org/model', 'revision': 'abc', 'local_path': str(folder), 'files': [{'name': 'weights', 'bytes': 4}]}])
            self.assertEqual(load(root, spec)[0]['revision'], 'abc')
            with patch('claim_runner.prepared.digest', side_effect=AssertionError('No weight reads during inference')):
                load(root, spec)
            (folder / 'weights').write_bytes(b'fail')
            load(root, spec)  # Same-size corruption is checked only during preparation.
            with self.assertRaises(ValueError):
                load(root, spec, verify_hashes=True)
            (folder / 'weights').write_bytes(b'wrong size')
            load(root, spec)
            with self.assertRaises(ValueError):
                load(root, spec, verify_hashes=True)
            (folder / 'weights').unlink()
            load(root, spec)
            with self.assertRaises(ValueError):
                load(root, spec, verify_hashes=True)

if __name__ == '__main__':
    unittest.main()
