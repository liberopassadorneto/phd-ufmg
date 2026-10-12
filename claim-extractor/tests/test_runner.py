"""CPU-only checks of benchmark integrity, failure recovery, and cleanup."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from claim_runner.catalog import MODELS, select_models
from claim_runner.inputs import fit_aps, read_aps, read_transcript, split_text
from claim_runner.resources import (GIB, choose_staging, cleanup_staging, create_staging,
                                    directory_size)
from claim_runner.worker import render_prompt
from claim_runner.outputs import write_outputs, processing
import run_models

ROOT = Path(__file__).resolve().parents[1]


class InputTests(unittest.TestCase):
    def test_oversized_aps_sentence_is_split_without_dropping_transcript_text(self):
        sentence = "Long subtitle without punctuation " * 50
        records = [{"chunk_id": "original", "sentences": [sentence],
                    "messages": [{"role": "user", "content": f"<s> {sentence} </s>"}]}]
        chunks = fit_aps(records, lambda messages: len(messages[0]["content"]) <= 100)
        self.assertGreater(len(chunks), 1)
        self.assertEqual("".join(s for c in chunks for s in c["sentences"]), sentence)
        self.assertTrue(all(len(c["messages"][0]["content"]) <= 100 for c in chunks))

    def test_frozen_aps_prompts_are_unchanged_when_they_fit(self):
        english = read_transcript(ROOT / "automatic.en.txt")["text"]
        records = read_aps(ROOT / "automatic.en.aps-input.jsonl", english)["records"]
        self.assertEqual(fit_aps(records, lambda messages: True), records)

    def test_input_alias_accepts_english_video_srt(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "video.en.srt"
            source.write_text("1\n00:00:00,000 --> 00:00:03,000\nThe treatment reduces appetite.\n")
            args = run_models.parse_args(["--models", "detective-qwen3b", "--input", str(source)])
            inputs, aps = run_models.prepare_inputs(args)
            self.assertEqual(inputs["en"]["text"], "The treatment reduces appetite.")
            self.assertIsNone(aps)

    def test_frozen_translation_matches_all_seven_chunks(self):
        english = read_transcript(ROOT / "automatic.en.txt")
        aps = read_aps(ROOT / "automatic.en.aps-input.jsonl", english["text"])
        self.assertEqual(len(aps["records"]), 7)
        self.assertEqual(aps["sentence_count"], 19)
        self.assertEqual(" ".join(s for c in aps["records"] for s in c["sentences"]), english["text"])

    def test_srt_removes_only_caption_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "input.srt"
            path.write_text("1\r\n00:00:00,000 --> 00:00:01,000\r\nDrug A.\r\n\r\n"
                            "2\r\n00:00:01,000 --> 00:00:02,000\r\n2026 cases.\r\n")
            self.assertEqual(read_transcript(path)["text"], "Drug A. 2026 cases.")

    def test_character_and_prompt_limits_preserve_every_character(self):
        text = "First sentence. Another sentence with a longwordwithoutboundarieshere. Last sentence."
        chunks = split_text(text, lambda t: len("PROMPT:" + t) <= 31, max_characters=30)
        self.assertEqual("".join(c["text"] for c in chunks), text)
        self.assertTrue(all(len(c["text"]) <= 24 for c in chunks))
        self.assertEqual(chunks[0]["source_start"], 0)
        for left, right in zip(chunks, chunks[1:]):
            self.assertEqual(left["source_end"], right["source_start"])
        self.assertEqual(chunks[-1]["source_end"], len(text))

    def test_prompt_with_no_source_budget_fails(self):
        with self.assertRaises(ValueError):
            split_text("text", lambda t: False)

    def test_inconsistent_aps_rejected(self):
        with self.assertRaises(ValueError):
            read_aps(ROOT / "automatic.en.aps-input.jsonl", "different transcript")


class CatalogTests(unittest.TestCase):
    def test_small_extractors_have_enough_output_budget_for_full_transcript_json(self):
        args = run_models.parse_args(["--models", "gemma-2b-aps,detective-qwen3b"])
        self.assertTrue(all(model.max_new_tokens >= 4096 for model in args.selected))
        self.assertGreater(args.context_tokens, max(model.max_new_tokens for model in args.selected))
    def test_all_twelve_checkpoint_ids_come_from_document(self):
        document = (ROOT / "knowledge-base/all_models.md").read_text()
        self.assertEqual(len(select_models("all")), 12)
        self.assertEqual(len({spec.repo for spec in MODELS}), 12)
        for spec in MODELS:
            self.assertIn(spec.repo, document)

    def test_alias_and_id_select_once_in_requested_order(self):
        self.assertEqual([m.alias for m in select_models(
            "detective-qwen3b,google/gemma-2b-aps-it,gemma-2b-aps")],
            ["detective-qwen3b", "gemma-2b-aps"])
        for value in ("all,gemma-2b-aps", "", "missing"):
            with self.assertRaises(ValueError):
                select_models(value)

    def test_listing_works_without_model_runtime(self):
        process = subprocess.run([sys.executable, str(ROOT / "run_models.py"), "--list-models"],
                                 capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(len(process.stdout.splitlines()), 12)


class CleanupTests(unittest.TestCase):
    def test_only_owned_staging_removed(self):
        with tempfile.TemporaryDirectory() as folder:
            parent = Path(folder)
            original = parent / "existing-model"
            original.mkdir()
            (original / "weights").write_text("preserve")
            staging = create_staging(parent, "owner")
            (staging / "weights").write_text("temporary")
            with self.assertRaises(RuntimeError):
                cleanup_staging(staging, parent, "different-owner")
            with self.assertRaises(RuntimeError):
                cleanup_staging(original, parent, "owner")
            cleanup_staging(staging, parent, "owner")
            self.assertFalse(staging.exists())
            self.assertEqual((original / "weights").read_text(), "preserve")

    def test_symlink_replacement_is_never_followed(self):
        with tempfile.TemporaryDirectory() as folder:
            parent = Path(folder)
            target = create_staging(parent, "owner")
            link = parent / "claim-model-symlink"
            link.symlink_to(target, target_is_directory=True)
            with self.assertRaises(RuntimeError):
                cleanup_staging(link, parent, "owner")
            self.assertTrue(target.exists())

    def test_storage_estimate_counts_hardlinked_weights_once(self):
        with tempfile.TemporaryDirectory() as folder:
            parent = Path(folder)
            a = parent / "a"
            a.write_bytes(b"123456")
            (parent / "b").hardlink_to(a)
            self.assertEqual(directory_size(parent), 6)

    def test_ram_staging_accounts_for_weights_and_loading_together(self):
        with tempfile.TemporaryDirectory() as folder:
            disk = Path(folder)
            ram = disk / "ram"
            ram.mkdir()
            psutil = SimpleNamespace(virtual_memory=lambda: SimpleNamespace(available=69 * GIB),
                disk_partitions=lambda all: [SimpleNamespace(mountpoint=str(ram), fstype="tmpfs")])
            with patch.dict(sys.modules, psutil=psutil), patch(
                "claim_runner.resources.shutil.disk_usage",
                side_effect=lambda p: SimpleNamespace(free=(36 if p == ram else 27) * GIB)):
                self.assertEqual(choose_staging(29 * GIB, 22 * GIB, disk, ram, 5 * GIB, 8 * GIB),
                                 (ram, "tmpfs"))
                with self.assertRaises(RuntimeError):
                    choose_staging(29 * GIB, 35 * GIB, disk, ram, 5 * GIB, 8 * GIB)


class OutputTests(unittest.TestCase):
    def test_json_output_is_the_unmodified_model_response(self):
        with tempfile.TemporaryDirectory() as folder:
            raw = '{  "claims": ["Drug A."] }'
            paths = write_outputs(Path(folder), "detective", [raw])
            self.assertEqual([p.name for p in paths], ["output.json"])
            self.assertEqual(paths[0].read_text(), raw)

    def test_partial_json_is_preserved_without_repair(self):
        with tempfile.TemporaryDirectory() as folder:
            raw = '{"claims": ['
            paths = write_outputs(Path(folder), "detective", [raw])
            self.assertEqual(paths[0].read_text(), raw)
            record = {"model": {"repo": "example", "adapter": "detective"}, "status": "partial",
                      "attempts": [{"mode": "fp16", "worker": {"truncated_chunks": 1},
                                    "resources": {}}]}
            report = processing(record, paths)
            self.assertFalse(report["output_valid_json"])
            self.assertIn("incomplete", report["warning"])

    def test_aps_retains_all_raw_chunks_in_order_without_txt(self):
        with tempfile.TemporaryDirectory() as folder:
            blocks = ["PROPOSITIONS:\n<s>\n- A.\n</s>", "PROPOSITIONS:\n<s>\n- B.\n</s>"]
            paths = write_outputs(Path(folder), "aps", blocks)
            self.assertEqual([p.name for p in paths], ["output.raw"])
            self.assertEqual(paths[0].read_text(), "\n\n".join(blocks))

    def test_json_chunks_keep_each_native_object_in_its_own_file(self):
        with tempfile.TemporaryDirectory() as folder:
            blocks = ['{"claims": ["A"]}', '{"claims": ["B"]}']
            paths = write_outputs(Path(folder), "detective", blocks)
            self.assertEqual([p.name for p in paths], ["output-001.json", "output-002.json"])
            self.assertEqual([p.read_text() for p in paths], blocks)

    def test_broken_nvml_measurement_does_not_report_zero_vram(self):
        record = {"model": {"repo": "example", "adapter": "aps"}, "status": "success",
                  "attempts": [{"mode": "fp16", "worker": {"torch_load_peak_allocated_bytes": 5 * GIB},
                                "resources": {"gpu_process_vram_peak_bytes": 0}}]}
        report = processing(record, [])
        self.assertEqual(report["vram_peak_gib"], 5)
        self.assertEqual(report["vram_measurement"], "PyTorch allocated memory")

    def test_sagesse_uses_published_template_and_empty_context(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            fence = chr(96) * 3
            (path / "README.md").write_text(fence + "text\n### Instruction:\nExtract claims.\n"
                "Submission:\n<submission>\nParent:\n<parent-comment>\nComment:\n<input-comment>\n" + fence)
            result = render_prompt({"adapter": "sagesse"}, None, "Source.", path)
            self.assertIn("Comment:\nSource.", result)
            self.assertNotIn("<submission>", result)


class SupervisorTests(unittest.TestCase):
    def test_public_results_contain_only_native_output_and_processing(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            output = root / "results"

            def fake_run(args, spec, run_dir, *_args):
                attempt = run_dir / spec.alias / "attempt"
                attempt.mkdir(parents=True)
                write_outputs(attempt, spec.adapter, ["PROPOSITIONS:\n<s>\n- A.\n</s>"
                              if spec.adapter == "aps" else '{"claims": ["A"]}'])
                return {"alias": spec.alias, "model": spec.record(), "status": "success",
                        "selected_attempt": str(attempt), "attempts": [{
                            "directory": str(attempt), "mode": "fp16", "worker": {
                                "inference_seconds": 1.5, "gpu": "test GPU",
                                "torch_load_peak_allocated_bytes": GIB}, "resources": {}}]}

            with patch.object(run_models, "run_one", side_effect=fake_run), \
                 patch.object(run_models.signal, "signal"):
                code = run_models.main(["--models", "gemma-2b-aps,detective-qwen3b",
                                        "--output-dir", str(output),
                                        "--staging-dir", str(root / "temporary")])
            self.assertEqual(code, 0)
            self.assertEqual(sorted(str(p.relative_to(output)) for p in output.rglob("*") if p.is_file()),
                             ["detective-qwen3b/output.json", "detective-qwen3b/processing.json",
                              "gemma-2b-aps/output.raw", "gemma-2b-aps/processing.json"])
            self.assertEqual(list((root / "temporary").iterdir()), [])

    def _run_with_fake_failure(self, folder, failure=None, retry=False):
        args = run_models.parse_args(["--models", "gemma-2b-aps", "--staging-dir", str(folder / "staging")])
        inputs, aps = run_models.prepare_inputs(args)
        state = {"setup": {"wall_seconds": 0}}
        manifest = {"repo": args.selected[0].repo, "revision": "pinned", "files": [], "download_bytes": 0}

        def download(_manifests, staging):
            (staging / "partial-weights").write_text("weights")
            if failure:
                raise failure
            return [{**manifest, "local_path": str(staging)}]

        calls = []
        def command(_command, output, *_args):
            calls.append(output)
            if retry and len(calls) == 1:
                worker = {"status": "failed", "retry_with_offload": True, "error": "OOM"}
                code = 42
            else:
                worker = {"status": "success", "inference_seconds": 1}
                code = 0
            (output / "worker-result.json").write_text(json.dumps(worker))
            return {"returncode": code, "resources": {}}

        class FakeMonitor:
            def __init__(self, *args): pass
            def start(self): return self
            def attach(self, _pid): pass
            def stop(self): return {}

        with patch.object(run_models, "ensure_runtime", return_value=state), \
             patch.object(run_models, "repository_manifest", return_value=manifest), \
             patch.object(run_models, "choose_staging", return_value=(args.staging_dir, "disk")), \
             patch.object(run_models, "download_repositories", side_effect=download), \
             patch.object(run_models, "Monitor", FakeMonitor), \
             patch.object(run_models, "command_record", side_effect=command), \
             patch.dict(sys.modules, psutil=SimpleNamespace(
                 virtual_memory=lambda: SimpleNamespace(available=128 * GIB))):
            result = run_models.run_one(args, args.selected[0], folder, inputs, aps, {})
        self.assertEqual(list(args.staging_dir.iterdir()), [])
        return result, calls

    def test_download_failure_and_interrupt_cleanup_owned_weights(self):
        for failure in (RuntimeError("connection dropped"), KeyboardInterrupt()):
            with self.subTest(failure=type(failure).__name__), tempfile.TemporaryDirectory() as folder:
                result, calls = self._run_with_fake_failure(Path(folder), failure=failure)
                self.assertTrue(result["staging_removed"])
                self.assertEqual(result["status"], "interrupted" if isinstance(failure, KeyboardInterrupt) else "failed")
                self.assertEqual(calls, [])

    def test_oom_retries_in_new_attempt_without_overwriting_first(self):
        with tempfile.TemporaryDirectory() as folder:
            result, calls = self._run_with_fake_failure(Path(folder), retry=True)
            self.assertEqual(result["status"], "success")
            self.assertEqual([a["mode"] for a in result["attempts"]], ["fp16", "offload"])
            self.assertEqual(len(calls), 2)
            self.assertTrue(all((path / "worker-result.json").is_file() for path in calls))


if __name__ == "__main__":
    unittest.main()
