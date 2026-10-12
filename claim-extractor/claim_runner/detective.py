"""Detective's published JSON fields, constrained during generation."""

import json
import re

from .inputs import split_text

CHUNK_CHARACTERS = 600
CHUNK_SENTENCES = 3
REPETITION_PENALTY = 1.1


def split_input(text, fits):
    # Preserve every character while limiting the amount to extract per response.
    return split_text(text, lambda part: fits(part) and len(
        re.split(r"(?<=[.!?])\s+", part.strip())) <= CHUNK_SENTENCES,
        max_characters=CHUNK_CHARACTERS)


def output_schema(model_path):
    # The author's schema.json contains enums, not a JSON Schema. The object
    # structure below follows README.md/prompt.txt; bounds prevent runaway text.
    enums = json.loads((model_path / "schema.json").read_text())["enums"]

    def string(maximum):
        return {"type": "string", "minLength": 1, "maxLength": maximum}

    def array(item, minimum, maximum):
        return {"type": "array", "items": item, "minItems": minimum, "maxItems": maximum}

    def obj(properties):
        return {"type": "object", "properties": properties,
                "required": list(properties), "additionalProperties": False}

    claim = obj({
        "id": {"type": "integer"}, "claim": string(180),
        "claim_type": {"type": "string", "enum": enums["claim_type"]},
        "category": string(80),
        "importance": {"type": "string", "enum": enums["importance"]},
        "stance": {"type": "string", "enum": enums["stance"]},
        "sentiment": {"type": "string", "enum": enums["sentiment"]},
        "evidence_span": string(CHUNK_CHARACTERS), "confidence": {"type": "number"},
        "verification_questions": array(string(160), 3, 6),
    })
    contradiction = obj({
        "claim_a": {"type": "integer"}, "claim_b": {"type": "integer"},
        "relation": {"type": "string", "enum": enums["relation"]},
        "explanation": string(240),
    })
    return obj({
        "summary": string(500),
        "publication_date": {"anyOf": [string(80), {"type": "null"}]},
        "keywords": array(string(80), 3, 12),
        "claims": array(claim, 1, 15), "contradictions": array(contradiction, 0, 15),
    })


def prefix_function(tokenizer_data, schema, eos_token_id):
    from lmformatenforcer import JsonSchemaParser
    from lmformatenforcer.characterlevelparser import CharacterLevelParserConfig
    from lmformatenforcer.integrations.transformers import build_transformers_prefix_allowed_tokens_fn

    parser = JsonSchemaParser(schema, config=CharacterLevelParserConfig(
        force_json_field_order=True, max_consecutive_whitespaces=2))
    allowed = build_transformers_prefix_allowed_tokens_fn(tokenizer_data, parser)

    def prefix(batch_id, input_ids):
        tokens = allowed(batch_id, input_ids)
        # Once the entire object is complete, stop rather than emitting padding
        # whitespace. The saved response remains exactly what the model emitted.
        return [eos_token_id] if eos_token_id in tokens else tokens

    return prefix


def output_issues(raw, source):
    """Flag card guarantees without repairing, deduplicating or rewriting output."""
    try:
        document = json.loads(raw)
        claims = document["claims"]
        issues = []
        if not 1 <= len(claims) <= 15:
            issues.append("claim count outside 1–15")
        texts = [c["claim"].strip().casefold() for c in claims]
        if len(set(texts)) != len(texts):
            issues.append("duplicate claims")
        if [c["id"] for c in claims] != list(range(len(claims))):
            issues.append("claim ids are not sequential")
        if any(not c["evidence_span"] or c["evidence_span"] not in source for c in claims):
            issues.append("evidence_span is not verbatim input")
        if any(not 0 <= c["confidence"] <= 1 for c in claims):
            issues.append("confidence outside 0–1")
        if any(not 3 <= len(c["verification_questions"]) <= 6 for c in claims):
            issues.append("verification question count outside 3–6")
        if any(c[key] not in range(len(claims)) for c in document["contradictions"]
               for key in ("claim_a", "claim_b")):
            issues.append("contradiction references an unknown claim")
        return issues
    except (ValueError, KeyError, TypeError, AttributeError):
        return ["invalid or incomplete Detective JSON"]
