"""Metadata declared by each model's own run.py; no inference defaults here."""

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class ModelSpec:
    alias: str
    repo: str
    parameters_b: float
    precision: str
    language: str
    default_input: str
    default_output: str
    output_format: str
    task: str
    causal: bool
    sources: dict[str, str]
    generation: dict = field(default_factory=dict)
    base_repo: str | None = None
    revision: str | None = None
    requires_prompt: bool = False
    input_configuration: dict = field(default_factory=dict)
    hardware_configuration: dict = field(default_factory=dict)

    @property
    def runtime(self):
        return self.alias

    def record(self):
        return {**asdict(self), "runtime": self.runtime,
                "model_card": f"https://huggingface.co/{self.repo}"}
