"""Resolve revisions and download just one checkpoint's necessary files."""

import os
import hashlib
from pathlib import Path, PurePosixPath


def repository_manifest(repo: str, revision: str | None = None) -> dict:
    from huggingface_hub import HfApi, hf_hub_url, get_token
    from huggingface_hub.utils import build_hf_headers
    import requests

    info = HfApi().model_info(repo, revision=revision, files_metadata=True)
    sizes = {s.rfilename: s.size for s in info.siblings}
    indices = ("model.safetensors.index.json", "pytorch_model.bin.index.json")
    index_name = next((name for name in indices if name in sizes), None)
    if index_name:
        response = requests.get(hf_hub_url(repo, index_name, revision=info.sha),
                                headers=build_hf_headers(token=get_token()), timeout=60)
        response.raise_for_status()
        index = response.json()
        required = sorted(set(index["weight_map"].values())) + [index_name]
    else:
        weight = next((name for name in ("model.safetensors", "adapter_model.safetensors",
                                         "pytorch_model.bin", "adapter_model.bin")
                       if name in sizes), None)
        if weight is None:
            raise ValueError(f"No supported HF weight file in {repo}; GGUF is not used on this server")
        required = [weight]
    for name in required:
        p = PurePosixPath(name)
        if p.is_absolute() or ".." in p.parts or name not in sizes:
            raise ValueError(f"Invalid checkpoint file name: {name}")
    extras = {"config.json", "generation_config.json", "adapter_config.json",
              "tokenizer.json", "tokenizer_config.json", "tokenizer.model", "spiece.model",
              "special_tokens_map.json", "added_tokens.json", "vocab.json", "vocab.txt",
              "merges.txt", "chat_template.jinja", "README.md", "prompt.txt", "schema.json"}
    files = sorted(set(required) | (extras & sizes.keys()))
    unknown = [name for name in files if sizes[name] is None]
    if unknown:
        raise ValueError(f"Missing storage sizes for {repo}: {unknown}")
    return {"repo": repo, "revision": info.sha, "files": [
        {"name": name, "bytes": sizes[name]} for name in files],
        "download_bytes": sum(sizes[name] for name in files)}


def download_repositories(manifests: list[dict], staging: Path) -> list[dict]:
    os.environ["HF_HUB_DISABLE_XET"] = "1"
    os.environ["HF_XET_CACHE"] = str(staging / "xet")
    from huggingface_hub import hf_hub_download
    records = []
    for index, manifest in enumerate(manifests):
        persistent = os.environ.get("CLAIM_CHECKPOINT_CACHE")
        key = hashlib.sha256((manifest['repo'] + '@' + manifest['revision']).encode()).hexdigest()
        folder = Path(persistent) / key if persistent else staging / f"repository-{index}"
        folder.mkdir(parents=True, exist_ok=True)
        for file in manifest["files"]:
            print(f"Downloading {manifest['repo']} / {file['name']}", flush=True)
            path = Path(hf_hub_download(manifest["repo"], file["name"],
                                       revision=manifest["revision"], local_dir=folder,
                                       cache_dir=staging / "hub"))
            if path.stat().st_size != file["bytes"]:
                raise RuntimeError(f"Download size mismatch: {file['name']}")
        records.append({**manifest, "local_path": str(folder.resolve())})
    return records
