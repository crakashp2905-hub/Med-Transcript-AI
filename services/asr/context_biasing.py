"""Pinned clinical lexicon inputs for the local faster-whisper hotwords hook."""

import hashlib
import json
from pathlib import Path


LEXICON_SHA256 = "af4b321287acd7762f6a9f63fe1ca29c4fc71ce0c52eda0ef95288efbfa4d142"
LEXICON_PATH = (
    Path(__file__).resolve().parents[2]
    / "evaluation"
    / "lexicons"
    / "clinical-english-v1-e01.json"
)


def build_context_bias(terms, lexicon_path=LEXICON_PATH):
    if not isinstance(terms, list) or len(terms) > 8:
        raise ValueError("clinical_bias_terms_invalid")
    path = Path(lexicon_path)
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != LEXICON_SHA256:
        raise ValueError("clinical_bias_lexicon_integrity_failure")
    lexicon = json.loads(data)
    allowed = {entry["term"] for entry in lexicon.get("entries", [])}
    normalized = []
    for term in terms:
        if not isinstance(term, str) or term.lower() not in allowed:
            raise ValueError("clinical_bias_term_not_in_pinned_lexicon")
        canonical = next(
            entry["term"]
            for entry in lexicon["entries"]
            if entry["term"] == term.lower()
        )
        if canonical not in normalized:
            normalized.append(canonical)
    return {
        "status": "faster_whisper_hotwords_candidate",
        "hotwords": ", ".join(normalized),
        "terms": normalized,
        "lexicon_sha256": digest,
        "candidate_only": True,
        "text_mutation": False,
    }
