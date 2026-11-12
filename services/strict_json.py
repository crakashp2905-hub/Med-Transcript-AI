"""Bounded strict JSON for untrusted requests/model output; values remain unchanged."""

import json
import math


def loads(raw, *, max_bytes=8 * 1024 * 1024, max_depth=32):
    if isinstance(raw, bytes):
        if len(raw) > max_bytes:
            raise ValueError("json_size_exceeded")
        text = raw.decode("utf-8")
    else:
        text = raw
        if len(text.encode("utf-8")) > max_bytes:
            raise ValueError("json_size_exceeded")
    depth = 0
    quoted = escaped = False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            depth += 1
            if depth > max_depth:
                raise ValueError("json_depth_exceeded")
        elif char in "]}":
            depth -= 1

    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate_json_key")
            if not key.isascii():
                raise ValueError("non_ascii_schema_key")
            result[key] = value
        return result

    def invalid_constant(_value):
        raise ValueError("non_finite_json_number")

    value = json.loads(
        text, object_pairs_hook=object_pairs, parse_constant=invalid_constant
    )
    pending = [value]
    while pending:
        item = pending.pop()
        if isinstance(item, str):
            item.encode("utf-8")
        elif isinstance(item, float) and not math.isfinite(item):
            # Exponent overflow (1e999) is parsed by json as a float, rather
            # than visiting parse_constant like literal NaN/Infinity.
            raise ValueError("non_finite_json_number")
        elif isinstance(item, dict):
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
    return value
