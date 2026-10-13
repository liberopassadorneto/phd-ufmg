"""Shared memory, context and CLI plumbing. Model protocols live in run.py."""

import copy
from pathlib import Path


def stage(job, name):
    job["_stage"](name)


def loading_options(factory, path, job):
    import torch
    from transformers import AutoConfig, BitsAndBytesConfig

    config = AutoConfig.from_pretrained(path, local_files_only=True, trust_remote_code=False)
    model_class = factory._model_mapping[type(config)] if hasattr(factory, "_model_mapping") else factory
    mode = job["mode"]
    options = dict(config=config, local_files_only=True, trust_remote_code=False,
                   torch_dtype=torch.float32 if mode == "fp32" else torch.float16,
                   attn_implementation="sdpa" if getattr(model_class, "_supports_sdpa", False) else "eager",
                   device_map=None if mode == "offload" else {"": 0})
    if mode == "nf4":
        options["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16, bnb_4bit_use_double_quant=True)
    return options


def finish_loading(model, job):
    if job["mode"] == "offload":
        import torch
        from accelerate import cpu_offload
        stage(job, "loading_offload")
        missing = [name for name, value in (*model.named_parameters(), *model.named_buffers()) if value.is_meta]
        if missing:
            raise RuntimeError("Unloaded meta tensors before CPU offload: " + ", ".join(missing[:8]))
        cpu_offload(model, execution_device=torch.device("cuda:0"), offload_buffers=False)
    model.eval()
    return model


def generation_configuration(model, defaults, job):
    job['_generation_overrides'] = {key:job[key] for key in ('max_new_tokens', 'max_length')
                                    if job.get(key) is not None}
    config = copy.deepcopy(model.generation_config)
    if config is None:
        return None  # Token classification has no generation configuration.
    values = dict(defaults)
    if job.get("max_new_tokens") is not None:
        values.pop("max_length", None)
        values["max_new_tokens"] = job["max_new_tokens"]
    elif job.get("max_length") is not None:
        values.pop("max_new_tokens", None)
        values["max_length"] = job["max_length"]
        config.max_new_tokens = None
    for key, value in values.items():
        setattr(config, key, value)
    return config


def input_capacity(tokenizer, model, job, causal):
    candidates = []
    if job.get("context_tokens") is not None:
        candidates.append(job["context_tokens"])
    config = getattr(model.config, "text_config", model.config)
    for value in (getattr(config, "max_position_embeddings", None), tokenizer.model_max_length):
        if value and value < 1_000_000:
            candidates.append(value)
    if not candidates:
        raise ValueError("Checkpoint has no usable context limit; provide --context-tokens")
    limit = min(candidates)
    job['_context_limit'] = limit
    generation = job["_generation"]
    if not causal:
        return limit
    if job.get("max_length") is not None:
        capacity = min(limit - 1, job["max_length"] - 1)
    else:
        capacity = limit - (generation.max_new_tokens or generation.max_length)
    if capacity < 1:
        raise ValueError("Generation budget leaves no input space; provide a smaller output limit")
    return capacity


def decode_generation(tokenizer, generated, encoded, job, causal):
    """Output decoding/accounting; inference itself belongs to each run.py."""
    ids = generated[0, encoded["input_ids"].shape[1]:] if causal else generated[0]
    config = job["_generation"]
    eos = config.eos_token_id
    eos_ids = eos if isinstance(eos, list) else [eos]
    count = len(ids) if causal else len(ids) - 1  # seq2seq decoder start is not generated
    if config.max_new_tokens is not None:
        at_limit = count >= config.max_new_tokens
    else:
        maximum = config.max_length
        # Transformers adds the input length to its default 20-token budget.
        if causal and maximum == 20 and job.get("max_length") is None:
            maximum += encoded["input_ids"].shape[1]
        at_limit = generated.shape[1] >= maximum
    incomplete = at_limit and (len(ids) == 0 or ids[-1].item() not in eos_ids)
    return tokenizer.decode(ids, skip_special_tokens=True, clean_up_tokenization_spaces=False), incomplete


def entrypoint(spec, load_model, prepare_chunks, infer):
    import argparse
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--job", type=Path)
    parser.add_argument("--probe", type=Path)
    parser.add_argument("--quantized", action="store_true")
    internal, remaining = parser.parse_known_args()
    if internal.probe:
        from .worker import probe
        return probe(internal.quantized, internal.probe)
    if internal.job:
        from .worker import run
        return run(internal.job, spec, load_model, prepare_chunks, infer)
    from run_models import main
    # Direct entrypoints delegate downloads/metrics to the same supervisor.
    return main(remaining, model_alias=spec.alias)
