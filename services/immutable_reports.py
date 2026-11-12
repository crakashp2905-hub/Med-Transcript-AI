"""Write-once benchmark publication with explicit predecessor provenance."""

import hashlib
import json
from pathlib import Path


def publish_json_once(output, report, *, supersedes=None):
    """Publish a JSON report once; successors bind the exact previous bytes."""
    output = Path(output)
    predecessor = None
    if supersedes is not None:
        source = Path(supersedes)
        if not source.is_file():
            raise ValueError("report_predecessor_missing")
        if source.resolve() == output.resolve():
            raise ValueError("report_successor_must_use_new_path")
        predecessor = {
            "path": source.as_posix(),
            "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        }
    if not isinstance(report, dict):
        raise ValueError("report_must_be_json_object")
    value = dict(report)
    value["publication"] = {
        "schema_version": "immutable_report_publication_v1",
        "supersedes": predecessor,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    return value


def write_text_once(output, content):
    """Publish a rendered companion without replacing an existing artifact."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(content)
