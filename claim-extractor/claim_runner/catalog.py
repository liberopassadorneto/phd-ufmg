"""Explicit, deduplicated checkpoint registry from knowledge-base/all_models.md."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ModelSpec:
    alias: str
    repo: str
    adapter: str
    parameters_b: float
    precision: str = "fp16"
    language: str = "en"
    max_new_tokens: int = 4096
    task: str = "generative_claim_extraction"
    base_repo: str | None = None
    revision: str | None = None
    reference: str | None = None
    note: str = ""
    smaller: str | None = None

    @property
    def runtime(self) -> str:
        return self.alias

    def record(self):
        return {**asdict(self), "runtime": self.runtime,
                "model_card": f"https://huggingface.co/{self.repo}"}


MODELS = (
    ModelSpec("gemma-2b-aps", "google/gemma-2b-aps-it", "aps", 2.51,
              max_new_tokens=4096, task="abstractive_proposition_segmentation",
              revision="6526315a71d38bfbde56357466ddcc27629cfd78"),
    ModelSpec("gemma-7b-aps", "google/gemma-7b-aps-it", "aps", 8.54,
              precision="nf4", max_new_tokens=4096,
              task="abstractive_proposition_segmentation", smaller="gemma-2b-aps"),
    ModelSpec("detective-qwen3b", "Luimas/claim-extractor-detective-qwen3b",
              "detective", 3.09, max_new_tokens=4096,
              note="Official prompt; shorter lossless chunks and card JSON constraints via lm-format-enforcer."),
    ModelSpec("newsscope", "nidhipandya/NewsScope-lora", "newsscope", 8.03,
              precision="nf4", max_new_tokens=4096,
              base_repo="meta-llama/Meta-Llama-3.1-8B-Instruct",
              reference="https://github.com/nidhip1611/NewsScope",
              note="PEFT adapter plus licensed Llama base; article input, usually 2–3 claims."),
    ModelSpec("babelscape-t5", "Babelscape/t5-base-summarization-claim-extractor",
              "t5", 0.223, precision="fp32", max_new_tokens=1024,
              reference="https://github.com/Babelscape/FENICE",
              note="Trained on summaries; supplied transcript is not automatically summarized."),
    ModelSpec("claimpt", "lfcc/bert-claimpt-chunk", "claimpt", 0.109,
              precision="fp32", language="pt", task="claim_span_identification",
              note="Token logits, not generative atomic claims; 512 tokens, stride 128."),
    ModelSpec("principled-4b", "principled-intelligence/claim-extractor-4B-q-2605",
              "principled", 4.66, precision="nf4", max_new_tokens=8192,
              reference="https://github.com/Principled-Intelligence/orbitals",
              smaller="principled-2b", note="Orbitals prompt; no fabricated service description or evidence."),
    ModelSpec("principled-2b", "principled-intelligence/claim-extractor-2B-q-2605",
              "principled", 2.27, max_new_tokens=8192,
              reference="https://github.com/Principled-Intelligence/orbitals"),
    ModelSpec("dongyru-mistral", "dongyru/Mistral-7B-Claim-Extractor",
              "generic", 7.24, precision="nf4",
              note="Empty model card: benchmark-authored extraction prompt; author protocol unknown."),
    ModelSpec("fc-claim-det-t5", "varadhbhatnagar/fc-claim-det-T5-base",
              "fc_t5", 0.223, precision="fp32", max_new_tokens=256,
              task="claim_normalization_summarization",
              reference="https://github.com/varadhbhatnagar/FC-Claim-Det",
              note="P-MRR-HRR preprocessing and six beams; output budget extended for transcripts beyond the author's 5–15-token example."),
    ModelSpec("sagesse-mistral", "SAGESSE-EPFL/Mistral-7b-claims-extraction",
              "sagesse", 7.25, precision="nf4",
              note="Official Reddit template with empty submission/parent context; source weights are FP32."),
    ModelSpec("mistral-instruct-v02", "mistralai/Mistral-7B-Instruct-v0.2",
              "generic", 7.24, precision="nf4", task="prompted_claim_extraction",
              note="Benchmark-authored prompt; not a FEVERFact fine-tuned checkpoint."),
)


def select_models(value: str) -> list[ModelSpec]:
    keys = [part.strip() for part in value.split(",")]
    if keys == ["all"]:
        return list(MODELS)
    mapping = {key: spec for spec in MODELS for key in (spec.alias, spec.repo)}
    selected = []
    for key in keys:
        if key not in mapping:
            raise ValueError(f"Unknown model {key!r}. Use --list-models; 'all' must be used alone.")
        spec = mapping[key]
        if spec not in selected:
            selected.append(spec)
    return selected
