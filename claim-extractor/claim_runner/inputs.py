"""Input validation and lossless, prompt-aware text splitting."""

import hashlib
import os
import json
import re
from pathlib import Path


def read_transcript(path: Path) -> dict:
    data = path.read_bytes()
    raw = data.decode("utf-8-sig")
    if path.suffix.lower() == ".srt":
        captions = []
        for block in re.split(r"\n\s*\n", raw.replace("\r\n", "\n")):
            lines = [line.strip() for line in block.splitlines() if line.strip()]
            if lines and lines[0].isdigit():
                lines = lines[1:]
            if lines and "-->" in lines[0]:
                lines = lines[1:]
            if lines:
                captions.append(" ".join(lines))
        text = " ".join(captions)
    elif path.suffix.lower() == ".txt":
        text = raw
    else:
        raise ValueError(f"Expected .txt or .srt: {path}")
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        raise ValueError(f"Empty transcript: {path}")
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(data).hexdigest(),
            "text": text, "format": path.suffix.lower()[1:]}


def read_aps(path: Path, english: str) -> dict:
    data = path.read_bytes()
    records = []
    sentences = []
    seen = set()
    for number, line in enumerate(data.decode("utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        record = json.loads(line)
        messages = record.get("messages")
        if not isinstance(messages, list) or len(messages) != 1 or messages[0].get("role") != "user":
            raise ValueError(f"APS line {number}: expected one user message")
        content = messages[0].get("content", "")
        groups = re.findall(r"<s>\s*(.*?)\s*</s>", content, re.S)
        if not groups or re.sub(r"<s>.*?</s>", "", content, flags=re.S).strip():
            raise ValueError(f"APS line {number}: invalid sentence markers")
        chunk_id = record.get("chunk_id", f"chunk_{len(records) + 1:04d}")
        if chunk_id in seen:
            raise ValueError(f"Duplicate APS chunk_id: {chunk_id}")
        seen.add(chunk_id)
        records.append({"chunk_id": chunk_id, "messages": messages, "sentences": groups})
        sentences.extend(groups)
    if not records or " ".join(sentences) != english:
        raise ValueError("APS prompts do not exactly reproduce the normalized English transcript")
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(data).hexdigest(),
            "records": records, "sentence_count": len(sentences)}


def make_aps(english: str, data_dir: Path) -> dict:
    import nltk
    data_dir.mkdir(parents=True, exist_ok=True)
    nltk.data.path.insert(0, str(data_dir))
    try:
        sentences = nltk.sent_tokenize(english, language="english")
    except LookupError:
        if os.environ.get("CLAIM_OFFLINE") == "1":
            raise RuntimeError("Missing prepared NLTK punkt_tab; rerun prepare-models.py")
        if not nltk.download("punkt_tab", download_dir=str(data_dir), quiet=True):
            raise RuntimeError("Could not download NLTK punkt_tab for custom APS input")
        sentences = nltk.sent_tokenize(english, language="english")
    return {"path": None, "sha256": None, "sentence_count": len(sentences),
            "records": [{"chunk_id": "chunk_0001", "sentences": sentences,
                         "messages": [{"role": "user", "content": "\n".join(
                             f"<s> {sentence} </s>" for sentence in sentences)}]}]}



def split_text(text: str, fits, max_characters: int | None = None) -> list[dict]:
    """Keep every source character; prefer sentence/word boundaries over hard cuts."""
    result = []
    start = 0
    while start < len(text):
        remaining = text[start:]
        upper = min(len(remaining), max_characters or len(remaining))
        if fits(remaining[:upper]):
            size = upper
        else:
            low, high = 1, upper
            size = 0
            while low <= high:
                middle = (low + high) // 2
                if fits(remaining[:middle]):
                    size, low = middle, middle + 1
                else:
                    high = middle - 1
            if not size:
                raise ValueError("Prompt plus output reservation leaves no room for source text")
        if size < len(remaining):
            boundaries = list(re.finditer(r"[.!?]\s+", remaining[:size]))
            if boundaries and boundaries[-1].end() >= size // 2:
                size = boundaries[-1].end()
            else:
                boundary = remaining.rfind(" ", 0, size)
                if boundary >= size // 2 and boundary > 0:
                    size = boundary + 1
        while size and not fits(remaining[:size]):
            size -= 1
        if not size:
            raise ValueError("Unable to fit a nonempty input chunk")
        result.append({"chunk_id": f"chunk_{len(result) + 1:04d}", "text": remaining[:size],
                       "source_start": start, "source_end": start + size})
        start += size
    return result


def fit_aps(records: list[dict], fits) -> list[dict]:
    """Keep frozen prompts when they fit; split oversized sentences without loss."""
    chunks = []

    def messages(sentences):
        return [{"role": "user", "content": "\n".join(f"<s> {s} </s>" for s in sentences)}]

    for record in records:
        if fits(record["messages"]):
            chunks.append(record)
            continue
        batch = []
        for sentence in record["sentences"]:
            parts = split_text(sentence, lambda part: fits(messages([part])))
            for part in parts:
                text = part["text"]
                if batch and not fits(messages(batch + [text])):
                    chunks.append({"messages": messages(batch), "sentences": batch})
                    batch = []
                batch.append(text)
        if batch:
            chunks.append({"messages": messages(batch), "sentences": batch})
    return [{**chunk, "chunk_id": f"chunk_{index:04d}"} for index, chunk in enumerate(chunks, 1)]
