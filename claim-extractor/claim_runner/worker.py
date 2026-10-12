"""Isolated CUDA worker. Invoked by run_models.py in the selected uv runtime."""

import argparse
import hashlib
import importlib.metadata
import json
import os
import re
import resource
import sys
import time
import traceback
from pathlib import Path

from .inputs import split_text
from .resources import GIB, write_json


def probe(quantized: bool, destination: Path) -> int:
    import torch
    import transformers
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable; no model weights were downloaded")
    x = torch.tensor([1., 2.], device="cuda", dtype=torch.float16)
    if (x * 2).tolist() != [2., 4.]:
        raise RuntimeError("FP16 CUDA operation failed")
    quantization = None
    if quantized:
        import bitsandbytes as bnb
        layer = bnb.nn.Linear4bit(64, 64, bias=False, compute_dtype=torch.float16,
                                 quant_type="nf4", compress_statistics=True).to("cuda")
        with torch.inference_mode():
            y = layer(torch.ones(1, 64, device="cuda", dtype=torch.float16))
        torch.cuda.synchronize()
        if not torch.isfinite(y).all().item():
            raise RuntimeError("NF4 CUDA operation produced nonfinite values")
        quantization = bnb.__version__
    write_json(destination, {"torch": torch.__version__, "transformers": transformers.__version__,
                             "bitsandbytes": quantization, "cuda": torch.version.cuda,
                             "gpu": torch.cuda.get_device_name(0),
                             "compute_capability": list(torch.cuda.get_device_capability(0)),
                             "total_vram_bytes": torch.cuda.get_device_properties(0).total_memory})
    return 0


GENERIC_PROMPT = (
    "Extract the factual claims asserted in the text below. Split compound claims into "
    "atomic statements and make each statement understandable on its own using only "
    "the supplied text. Preserve attribution, negation, uncertainty, and numbers. "
    "Do not answer questions or add facts. Return a JSON object with a 'claims' key "
    "containing a list of strings.\n\nTEXT:\n"
)


def render_prompt(spec, tokenizer, text, model_path):
    kind = spec["adapter"]
    if kind in ("t5", "fc_t5"):
        return text
    if kind == "principled":
        from orbitals.claim_extractor.prompting import build_prompt
        return build_prompt(tokenizer, text, ai_service_description=None, skip_evidences=True)
    if kind == "newsscope":
        return ("Extract structured claims from this news article.\n"
                "Return valid JSON with: domain, headline, key_points, whos_involved, "
                "how_it_unfolded, claims.\n\nArticle:\n" + text + "\n\nJSON Output:")
    if kind == "sagesse":
        readme = (model_path / "README.md").read_text(encoding="utf-8")
        fence = chr(96) * 3
        matches = re.findall(fence + r"[^\n]*\n(.*?)" + fence, readme, flags=re.S)
        template = next((m for m in matches if "### Instruction:" in m and "<input-comment>" in m), None)
        if template is None:
            raise ValueError("Pinned SAGESSE README does not contain the published input template")
        return template.replace("<submission>", "").replace("<parent-comment>", "").replace("<input-comment>", text)
    content = ((model_path / "prompt.txt").read_text(encoding="utf-8") + text
               if kind == "detective" else GENERIC_PROMPT + text)
    return tokenizer.apply_chat_template([{"role": "user", "content": content}],
                                         tokenize=False, add_generation_prompt=True)


def fc_preprocess(text):
    return re.sub(r"(?:[@#]\w+\s*)+", " ", text).strip()


def context_limit(tokenizer, model, configured, seq2seq=False):
    candidates = [configured]
    config = getattr(model.config, "text_config", model.config)
    value = getattr(config, "max_position_embeddings", None)
    if value and value < 1_000_000:
        candidates.append(value)
    if tokenizer.model_max_length < 1_000_000:
        candidates.append(tokenizer.model_max_length)
    if seq2seq:
        candidates.append(512)
    return min(candidates)


def load_model(job):
    import torch
    from transformers import (AutoConfig, AutoModelForCausalLM, AutoModelForSeq2SeqLM,
                              AutoModelForTokenClassification, AutoTokenizer, BitsAndBytesConfig)

    spec = job["spec"]
    paths = job["repositories"]
    path = paths[-1]["local_path"] if spec["base_repo"] else paths[0]["local_path"]
    tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True, trust_remote_code=False)
    if spec["adapter"] == "claimpt":
        factory = AutoModelForTokenClassification
    elif spec["adapter"] in ("t5", "fc_t5"):
        factory = AutoModelForSeq2SeqLM
    elif spec["adapter"] == "principled":
        from transformers import Qwen3_5ForConditionalGeneration
        factory = Qwen3_5ForConditionalGeneration
    else:
        factory = AutoModelForCausalLM
    mode = job["mode"]
    dtype = torch.float32 if mode == "fp32" else torch.float16
    config = AutoConfig.from_pretrained(path, local_files_only=True, trust_remote_code=False)
    model_class = factory._model_mapping[type(config)] if hasattr(factory, "_model_mapping") else factory
    attention = "sdpa" if getattr(model_class, "_supports_sdpa", False) else "eager"
    kwargs = {"local_files_only": True, "trust_remote_code": False,
              "config": config, "torch_dtype": dtype, "low_cpu_mem_usage": True,
              "attn_implementation": attention}
    if mode == "nf4":
        kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16, bnb_4bit_use_double_quant=True)
        kwargs["device_map"] = {"": 0}
    elif mode == "offload":
        kwargs["device_map"] = {"": "cpu"}
    else:
        kwargs["device_map"] = {"": 0}
    model = factory.from_pretrained(path, **kwargs)
    if spec["base_repo"]:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, paths[0]["local_path"], is_trainable=False,
                                           local_files_only=True)
    if mode == "offload":
        from accelerate import cpu_offload
        cpu_offload(model, execution_device=torch.device("cuda:0"), offload_buffers=True)
    model.eval()
    return model, tokenizer


def parse_generation(kind, text):
    if kind == "aps":
        groups = re.findall(r"<s>(.*?)</s>", text, flags=re.S)
        return {"groups": [[line.strip().removeprefix("- ").strip() for line in group.splitlines()
                             if line.strip()] for group in groups]} if groups else {
            "parse_error": "No APS output groups"}
    if kind in ("t5", "fc_t5"):
        return {"text": text}
    candidate = text.strip()
    if candidate.startswith(chr(96) * 3):
        lines = candidate.splitlines()
        candidate = "\n".join(lines[1:-1] if lines[-1].strip() == chr(96) * 3 else lines[1:])
    try:
        return {"value": json.loads(candidate)}
    except ValueError as exc:
        return {"parse_error": str(exc)}


def append_jsonl(stream, record):
    stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    stream.flush()
    os.fsync(stream.fileno())


def run(job_path: Path) -> int:
    job = json.loads(job_path.read_text(encoding="utf-8"))
    out = Path(job["output"])
    spec = job["spec"]
    result = {"status": "running", "mode": job["mode"], "chunks_completed": 0,
              "inference_seconds": 0.0, "parse_errors": 0, "truncated_chunks": 0}
    started = time.perf_counter()
    phase = "loading"
    load_started = None
    inference_started = None

    def save():
        result["total_worker_seconds"] = time.perf_counter() - started
        times = resource.getrusage(resource.RUSAGE_SELF)
        result["process_cpu_seconds"] = times.ru_utime + times.ru_stime
        result["process_max_rss_bytes"] = times.ru_maxrss * 1024
        write_json(out / "worker-result.json", result)

    def set_phase(value):
        nonlocal phase
        phase = value
        write_json(out / "phase.json", {"phase": value})

    try:
        import torch
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is unavailable")
        torch.manual_seed(job["seed"])
        torch.cuda.manual_seed_all(job["seed"])
        torch.set_num_threads(job["cpu_threads"])
        total = torch.cuda.get_device_properties(0).total_memory
        free, _ = torch.cuda.mem_get_info(0)
        budget = min(total, free) - job["gpu_reserve_bytes"]
        if budget < GIB:
            raise RuntimeError("Insufficient VRAM after the configured reserve")
        torch.cuda.set_per_process_memory_fraction(budget / total, device=0)
        torch.backends.cuda.enable_flash_sdp(False)
        torch.cuda.reset_peak_memory_stats(0)
        result["versions"] = {name: importlib.metadata.version(name)
                              for name in ("torch", "transformers", "accelerate")}
        result["gpu"] = torch.cuda.get_device_name(0)
        result["gpu_budget_bytes"] = budget
        set_phase("loading")
        load_started = time.perf_counter()
        model, tokenizer = load_model(job)
        torch.cuda.synchronize()
        result["load_seconds"] = time.perf_counter() - load_started
        result["model_memory_bytes"] = model.get_memory_footprint()
        result["torch_load_peak_allocated_bytes"] = torch.cuda.max_memory_allocated(0)
        result["torch_load_peak_reserved_bytes"] = torch.cuda.max_memory_reserved(0)
        torch.cuda.reset_peak_memory_stats(0)
        save()
        set_phase("preparing")
        source = job["input"]["text"]
        model_path = Path(job["repositories"][0]["local_path"])
        kind = spec["adapter"]
        is_seq2seq = kind in ("t5", "fc_t5")
        maximum = job["max_new_tokens"] or spec["max_new_tokens"]
        limit = context_limit(tokenizer, model, job["context_tokens"], is_seq2seq)
        effective_limit = limit if is_seq2seq or kind == "claimpt" else limit - maximum
        if effective_limit < 1:
            raise ValueError(f"Context budget {limit} must exceed output reservation {maximum}; "
                             "increase --context-tokens or reduce --max-new-tokens")
        config = {"mode": job["mode"], "seed": job["seed"], "input_context_limit": limit,
                  "max_new_tokens": maximum, "do_sample": kind == "newsscope",
                  "cpu_threads": job["cpu_threads"], "prompt_source": spec["reference"] or spec["model_card"],
                  "source_input": job["input"], "spec": spec, "repositories": job["repositories"],
                  "note": spec["note"], "attention": getattr(model.config, "_attn_implementation", None),
                  "thinking": False if kind == "principled" else None}
        write_json(out / "configuration.json", config)
        if kind == "claimpt":
            if min(limit, 512) <= 128 + tokenizer.num_special_tokens_to_add(pair=False):
                raise ValueError("ClaimPT context must accommodate its 128-token overlap")
            enc = tokenizer(source, return_tensors="pt", padding=True, truncation=True,
                            max_length=min(limit, 512), stride=128,
                            return_overflowing_tokens=True, return_offsets_mapping=True)
            chunks = [{"chunk_id": f"chunk_{i + 1:04d}", "window_index": i}
                      for i in range(len(enc["input_ids"]))]
        elif kind == "aps":
            chunks = job["aps"]["records"]
        else:
            transformed = fc_preprocess(source) if kind == "fc_t5" else source
            if not transformed:
                raise ValueError("Input became empty after model-specific preprocessing")
            config["preprocessed_text"] = transformed
            config["preprocessed_sha256"] = hashlib.sha256(transformed.encode()).hexdigest()
            write_json(out / "configuration.json", config)
            chunks = split_text(transformed,
                lambda text: len(tokenizer(render_prompt(spec, tokenizer, text, model_path))["input_ids"]) <= effective_limit,
                max_characters=4000 if kind == "detective" else None)
        result["chunks_expected"] = len(chunks)
        save()
        with (out / "effective-inputs.jsonl").open("w", encoding="utf-8") as inputs_stream, \
             (out / "raw.jsonl").open("w", encoding="utf-8") as raw_stream, \
             (out / "parsed.jsonl").open("w", encoding="utf-8") as parsed_stream:
            for chunk in chunks:
                chunk_id = chunk["chunk_id"]
                print(f"{spec['alias']}: {chunk_id}/{len(chunks)} ({job['mode']})", flush=True)
                if kind == "claimpt":
                    i = chunk["window_index"]
                    inputs = {key: value[i:i + 1].to("cuda")
                              for key, value in enc.items() if key in tokenizer.model_input_names}
                    input_record = {**chunk, "input_ids": inputs["input_ids"][0].tolist(),
                                    "offset_mapping": enc["offset_mapping"][i].tolist(),
                                    "language": spec["language"]}
                else:
                    prompt = (tokenizer.apply_chat_template(chunk["messages"], tokenize=False,
                              add_generation_prompt=True) if kind == "aps" else
                              render_prompt(spec, tokenizer, chunk["text"], model_path))
                    inputs = tokenizer(prompt, return_tensors="pt", add_special_tokens=kind not in (
                        "aps", "detective", "generic", "principled"))
                    if inputs["input_ids"].shape[1] > effective_limit:
                        raise ValueError(f"{chunk_id}: rendered prompt exceeds context budget; no truncation performed")
                    input_record = {**chunk, "prompt": prompt, "input_ids": inputs["input_ids"][0].tolist(),
                                    "language": spec["language"]}
                    inputs = {key: value.to("cuda") for key, value in inputs.items()}
                append_jsonl(inputs_stream, input_record)
                set_phase("inference")
                torch.cuda.synchronize()
                before = time.perf_counter()
                inference_started = before
                with torch.inference_mode():
                    if kind == "claimpt":
                        logits = model(**inputs).logits
                    else:
                        kwargs = {"do_sample": kind == "newsscope", "max_new_tokens": maximum}
                        if kind == "newsscope":
                            kwargs["temperature"] = 0.3
                        if kind == "fc_t5":
                            kwargs.update(num_beams=6, no_repeat_ngram_size=2,
                                          min_length=5, early_stopping=True)
                        if tokenizer.eos_token_id is not None and tokenizer.pad_token_id is None:
                            kwargs["pad_token_id"] = tokenizer.eos_token_id
                        generated = model.generate(**inputs, **kwargs)
                torch.cuda.synchronize()
                seconds = time.perf_counter() - before
                inference_started = None
                result["inference_seconds"] += seconds
                if kind == "claimpt":
                    import numpy as np
                    filename = f"{chunk_id}.logits.npz"
                    np.savez_compressed(out / filename, logits=logits.float().cpu().numpy(),
                                        input_ids=inputs["input_ids"].cpu().numpy(),
                                        offsets=enc["offset_mapping"][chunk["window_index"]].numpy())
                    ids = logits.argmax(dim=-1)[0].tolist()
                    raw = {"chunk_id": chunk_id, "logits_file": filename, "label_ids": ids,
                           "id2label": model.config.id2label, "inference_seconds": seconds}
                    parsed = {"chunk_id": chunk_id, "predicted_labels": [
                        model.config.id2label[label] for label in ids]}
                else:
                    new_ids = generated[0] if is_seq2seq else generated[0, inputs["input_ids"].shape[1]:]
                    ids = new_ids.tolist()
                    text = tokenizer.decode(ids, skip_special_tokens=True, clean_up_tokenization_spaces=False)
                    raw_text = tokenizer.decode(ids, skip_special_tokens=False, clean_up_tokenization_spaces=False)
                    eos = model.generation_config.eos_token_id or tokenizer.eos_token_id
                    eos = eos if isinstance(eos, list) else [eos]
                    reached_limit = len(ids) >= maximum and (not ids or ids[-1] not in eos)
                    raw = {"chunk_id": chunk_id, "generated_text": text, "raw_decoded_text": raw_text,
                           "generated_token_ids": ids, "inference_seconds": seconds,
                           "output_limit_reached": reached_limit}
                    parsed = {"chunk_id": chunk_id, **parse_generation(kind, text)}
                    result["truncated_chunks"] += int(reached_limit)
                    result["parse_errors"] += int("parse_error" in parsed)
                append_jsonl(raw_stream, raw)
                append_jsonl(parsed_stream, parsed)
                result["chunks_completed"] += 1
                result["torch_inference_peak_allocated_bytes"] = torch.cuda.max_memory_allocated(0)
                result["torch_inference_peak_reserved_bytes"] = torch.cuda.max_memory_reserved(0)
                save()
        result["status"] = "partial" if result["truncated_chunks"] else "success"
        set_phase("finished")
        save()
        return 0 if result["status"] == "success" else 1
    except Exception as exc:
        result.update(status="failed", error_type=type(exc).__name__, error=str(exc), failure_phase=phase)
        if load_started is not None and "load_seconds" not in result:
            result["load_seconds"] = time.perf_counter() - load_started
        if inference_started is not None:
            result["failed_chunk_seconds"] = time.perf_counter() - inference_started
            result["inference_seconds"] += result["failed_chunk_seconds"]
        try:
            import torch
            oom = isinstance(exc, torch.cuda.OutOfMemoryError)
            if torch.cuda.is_initialized():
                result["torch_failure_peak_allocated_bytes"] = torch.cuda.max_memory_allocated(0)
                result["torch_failure_peak_reserved_bytes"] = torch.cuda.max_memory_reserved(0)
        except Exception:
            oom = False
        result["retry_with_offload"] = oom or (job["mode"] == "nf4" and phase == "loading"
            and isinstance(exc, (RuntimeError, ImportError, ValueError)))
        traceback.print_exc()
        save()
        return 42 if result["retry_with_offload"] else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", type=Path)
    parser.add_argument("--probe", type=Path)
    parser.add_argument("--quantized", action="store_true")
    args = parser.parse_args()
    if args.probe:
        try:
            return probe(args.quantized, args.probe)
        except Exception:
            traceback.print_exc()
            return 1
    if not args.job:
        parser.error("--job or --probe is required")
    return run(args.job)


if __name__ == "__main__":
    sys.exit(main())
