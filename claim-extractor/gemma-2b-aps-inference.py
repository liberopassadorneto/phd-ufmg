#!/usr/bin/env python3
"""Run google/gemma-2b-aps-it on SRT or plain-text transcripts.

The runner follows the model card's APS input/output format, processes long
transcripts in small sentence batches, and writes reproducible JSON containing
the claims, source text, timing, model revision, and GPU-memory measurements.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

import nltk
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


MODEL_ID = "google/gemma-2b-aps-it"
MODEL_REVISION = "6526315a71d38bfbde56357466ddcc27629cfd78"
START_MARKER = "<s>"
END_MARKER = "</s>"
SEPARATOR = "\n"
LANGUAGE_NAMES = {"en": "english", "pt": "portuguese"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract atomic propositions from an SRT or TXT transcript."
    )
    parser.add_argument("input", type=Path, help="Input .srt or .txt file")
    parser.add_argument(
        "--output",
        type=Path,
        help="Output JSON path (default: output/<input>.claims.json)",
    )
    parser.add_argument(
        "--language",
        choices=sorted(LANGUAGE_NAMES),
        default="en",
        help="Transcript language used for sentence splitting (default: en)",
    )
    parser.add_argument(
        "--allow-unsupported-language",
        action="store_true",
        help="Allow exploratory inference outside English; invalid for benchmark use",
    )
    parser.add_argument(
        "--sentences-per-chunk",
        type=int,
        default=3,
        help="Number of source sentences per inference batch (default: 3)",
    )
    parser.add_argument(
        "--max-new-tokens",
        type=int,
        default=512,
        help="Maximum generated tokens per batch (default: 512)",
    )
    parser.add_argument(
        "--revision",
        default=MODEL_REVISION,
        help="Pinned Hugging Face model revision",
    )
    args = parser.parse_args()

    if args.sentences_per_chunk < 1:
        parser.error("--sentences-per-chunk must be at least 1")
    if args.max_new_tokens < 1:
        parser.error("--max-new-tokens must be at least 1")
    if args.language != "en" and not args.allow_unsupported_language:
        parser.error(
            "Gemma-APS is English-only. For an exploratory non-benchmark run, "
            "add --allow-unsupported-language."
        )
    return args


def parse_srt(text: str) -> tuple[str, int]:
    """Remove SRT sequence numbers/timestamps and join caption text in order."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    blocks = re.split(r"\n{2,}", normalized)
    captions: list[str] = []

    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        if lines[0].isdigit():
            lines = lines[1:]
        if lines and "-->" in lines[0]:
            lines = lines[1:]
        caption = " ".join(lines).strip()
        if caption:
            captions.append(caption)

    transcript = re.sub(r"\s+", " ", " ".join(captions)).strip()
    return transcript, len(captions)


def load_input(path: Path) -> tuple[str, dict[str, Any]]:
    raw = path.read_text(encoding="utf-8-sig")
    suffix = path.suffix.lower()

    if suffix == ".srt":
        transcript, cue_count = parse_srt(raw)
        metadata = {"format": "srt", "cue_count": cue_count}
    elif suffix == ".txt":
        transcript = re.sub(r"\s+", " ", raw).strip()
        metadata = {"format": "txt", "cue_count": None}
    else:
        raise ValueError("Input must have the .srt or .txt extension")

    if not transcript:
        raise ValueError("Input transcript is empty after preprocessing")

    metadata.update(
        {
            "path": str(path.resolve()),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "characters": len(transcript),
        }
    )
    return transcript, metadata


def create_propositions_input(sentences: list[str]) -> str:
    return SEPARATOR.join(
        f"{START_MARKER} {sentence} {END_MARKER}" for sentence in sentences
    )


def process_propositions_output(text: str) -> list[list[str]]:
    pattern = re.compile(
        f"{re.escape(START_MARKER)}(.*?){re.escape(END_MARKER)}", re.DOTALL
    )
    groups: list[list[str]] = []

    for grouped_output in re.findall(pattern, text):
        claims = []
        for line in grouped_output.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            claims.append(line[2:].strip() if line.startswith("- ") else line)
        groups.append(claims)

    return groups


def chunked(items: list[str], size: int) -> list[list[str]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def gibibytes(value: int) -> float:
    return round(value / 1024**3, 3)


def main() -> int:
    args = parse_args()
    started_at = time.perf_counter()
    transcript, input_metadata = load_input(args.input)
    nltk_language = LANGUAGE_NAMES[args.language]
    sentences = nltk.tokenize.sent_tokenize(transcript, language=nltk_language)
    batches = chunked(sentences, args.sentences_per_chunk)

    output_path = args.output or Path("output") / f"{args.input.stem}.claims.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available; this runner expects the GPU setup")

    print(f"Loading {MODEL_ID} at revision {args.revision} in FP16...", flush=True)
    load_started_at = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, revision=args.revision)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        revision=args.revision,
        device_map="auto",
        torch_dtype=torch.float16,
        low_cpu_mem_usage=True,
    )
    model.eval()
    load_seconds = time.perf_counter() - load_started_at
    torch.cuda.reset_peak_memory_stats()

    result_chunks: list[dict[str, Any]] = []
    flat_claims: list[dict[str, Any]] = []
    claim_number = 0
    inference_seconds = 0.0
    source_sentence_offset = 0

    for chunk_index, source_sentences in enumerate(batches, start=1):
        print(f"Processing chunk {chunk_index}/{len(batches)}...", flush=True)
        messages = [
            {
                "role": "user",
                "content": create_propositions_input(source_sentences),
            }
        ]
        inputs = tokenizer.apply_chat_template(
            messages,
            return_tensors="pt",
            add_generation_prompt=True,
            return_dict=True,
        ).to(model.device)

        inference_started_at = time.perf_counter()
        with torch.inference_mode():
            output = model.generate(
                **inputs,
                max_new_tokens=args.max_new_tokens,
                do_sample=False,
            )
        chunk_inference_seconds = time.perf_counter() - inference_started_at
        inference_seconds += chunk_inference_seconds

        generated_text = tokenizer.batch_decode(
            output[:, inputs["input_ids"].shape[1] :],
            skip_special_tokens=True,
        )[0]
        groups = process_propositions_output(generated_text)

        chunk_claims: list[dict[str, Any]] = []
        for group_index, claims in enumerate(groups):
            source_sentence_index = source_sentence_offset + group_index + 1
            source_sentence = (
                source_sentences[group_index]
                if group_index < len(source_sentences)
                else None
            )
            for claim in claims:
                claim_number += 1
                claim_record = {
                    "claim_id": f"claim_{claim_number:04d}",
                    "claim": claim,
                    "source_chunk_id": f"chunk_{chunk_index:04d}",
                    "source_sentence_index": source_sentence_index,
                    "source_sentence": source_sentence,
                }
                flat_claims.append(claim_record)
                chunk_claims.append(claim_record)

        result_chunks.append(
            {
                "chunk_id": f"chunk_{chunk_index:04d}",
                "source_sentence_start": source_sentence_offset + 1,
                "source_sentences": source_sentences,
                "raw_generation": generated_text,
                "claims": chunk_claims,
                "inference_seconds": round(chunk_inference_seconds, 3),
            }
        )
        source_sentence_offset += len(source_sentences)

    if len(result_chunks) != len(batches):
        raise RuntimeError("Not every input batch produced an output record")

    total_seconds = time.perf_counter() - started_at
    supported_language = args.language == "en"
    result = {
        "schema_version": "1.0",
        "model": {
            "id": MODEL_ID,
            "revision": args.revision,
            "dtype": "float16",
            "device": str(model.device),
            "gpu": torch.cuda.get_device_name(0),
        },
        "input": {
            **input_metadata,
            "language": args.language,
            "model_supports_language": supported_language,
            "benchmark_eligible": supported_language,
            "transcript": transcript,
            "sentence_count": len(sentences),
        },
        "configuration": {
            "sentences_per_chunk": args.sentences_per_chunk,
            "max_new_tokens": args.max_new_tokens,
            "do_sample": False,
        },
        "metrics": {
            "claim_count": len(flat_claims),
            "chunk_count": len(result_chunks),
            "model_load_seconds": round(load_seconds, 3),
            "inference_seconds": round(inference_seconds, 3),
            "total_seconds": round(total_seconds, 3),
            "peak_gpu_allocated_gib": gibibytes(torch.cuda.max_memory_allocated()),
            "peak_gpu_reserved_gib": gibibytes(torch.cuda.max_memory_reserved()),
        },
        "warnings": (
            []
            if supported_language
            else [
                "Gemma-APS is documented as English-only. This exploratory "
                "output is not eligible for the A/B/C scientific benchmark."
            ]
        ),
        "claims": flat_claims,
        "chunks": result_chunks,
    }

    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote {len(flat_claims)} claims to {output_path}")
    print(f"Inference time: {inference_seconds:.2f}s")
    print(
        "Peak GPU allocated: "
        f"{result['metrics']['peak_gpu_allocated_gib']:.2f} GiB"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
