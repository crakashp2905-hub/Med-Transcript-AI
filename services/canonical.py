"""Canonical semantic JSON hashing. Raw artifact byte hashes remain separate."""
import hashlib
import json


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def content_sha256(value):
    return hashlib.sha256(canonical_json(value).encode('utf-8')).hexdigest()
