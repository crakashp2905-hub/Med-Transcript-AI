"""Generate source-hashed pseudocode for current evidence graph algorithms."""

import argparse
import ast
import hashlib
import json
import subprocess
from pathlib import Path


ALGORITHMS = [
    {
        "id": "evidence_proposal_graph",
        "path": "services/evidence_graph.py",
        "function": "validate_proposal",
        "anchors": [
            "evidence_graph_source_required",
            "evidence_graph_duplicate_segment",
            "evidence_graph_invalid_source_link",
            "audio_to_transcript",
            "transcript_to_span",
            "span_to_fact",
            "complete_to_fact",
            "complete_to_export",
        ],
        "pseudocode": [
            "Require transcript ID and audio asset ID.",
            "Index transcript segments and reject duplicate segment IDs.",
            "For each fact, require a unique fact ID, a known segment, integer offsets, and an exact source-text quote match.",
            "Hash the transcript ID plus evidence span to identify a source span.",
            "Add audio→segment, segment→span, and span→fact edges; deduplicate shared edges.",
            "Validate graph node/edge invariants; return source hash and fact-level completeness only.",
        ],
    },
    {
        "id": "directed_graph_invariants",
        "path": "services/evidence_graph.py",
        "function": "validate_graph_invariants",
        "anchors": [
            "evidence_graph_nodes_invalid",
            "evidence_graph_edge_node_missing",
            "evidence_graph_edge_duplicate",
            "evidence_graph_tenant_missing",
            "evidence_graph_cross_tenant_edge",
            "evidence_graph_cycle_detected",
        ],
        "pseudocode": [
            "Require a non-empty, duplicate-free node set.",
            "For every edge, require present endpoints, an edge type, and a unique (from,to,type) tuple.",
            "When tenant labels are supplied, require both endpoints to be labeled and to share a tenant.",
            "Run Kahn's indegree queue traversal; reject unless every node is visited.",
            "Return node count, edge count, and acyclic=true only after all checks pass.",
        ],
    },
    {
        "id": "approved_export_hash_chain",
        "path": "services/evidence_graph.py",
        "function": "validate_approved_export",
        "anchors": [
            "evidence_graph_hash_chain_invalid",
            "evidence_graph_unexpected_amendment_parent",
            "evidence_graph_amendment_parent_invalid",
            "evidence_graph_note_fact_link_invalid",
            "evidence_graph_note_coverage_incomplete",
            "complete_to_export",
        ],
        "pseudocode": [
            "Recompute transcript and note hashes; bind note to transcript ID/hash and approval to exact note/transcript IDs/hashes.",
            "Require export ID and artifact hash; validate amendment parent linkage and hash when present.",
            "Validate source-linked facts against transcript spans and build evidence edges.",
            "Require note statements to reference known facts, then link fact→statement→export.",
            "Validate the completed graph and return only after the exact approval/export chain is consistent.",
        ],
    },
    {
        "id": "directional_source_coverage",
        "path": "services/review/engine.py",
        "function": "directional_coverage",
        "anchors": [
            "source_omission",
            "critical_source_omission",
            "unaccounted_source_content",
            "note_not_in_source",
            "source_not_in_note",
        ],
        "pseudocode": [
            "Partition verifier findings into source-to-note and note-to-source code sets.",
            "Keep finding ID, code, materiality, fact ID, and bounded source reference.",
            "Summarize deterministic coverage receipts and manual facts without treating them as clinical gold labels.",
            "Return directional findings; do not convert coverage into a clinical accuracy or false-alert rate.",
        ],
    },
]

DIAGRAM = """flowchart LR
  A[Audio asset] --> T[Transcript segment]
  T --> S[Exact evidence span]
  S --> F[Typed fact]
  F --> N[Note statement]
  N --> X[Approved export]
  V[Validate IDs, offsets, quote, hashes, tenant, and DAG] -. gates .-> T
  V -. gates .-> S
  V -. gates .-> F
  V -. gates .-> X"""

INVARIANT_DIAGRAM = """flowchart TD
  A[Node and edge IDs valid] --> B[Reject duplicate nodes/edges]
  B --> C[Reject missing or cross-tenant endpoints]
  C --> D[Kahn indegree traversal]
  D -->|visited all nodes| E[Return acyclic graph]
  D -->|cycle remains| F[Reject graph]"""


def build(root="."):
    root = Path(root).resolve()
    rows = []
    hashes = {}
    for algorithm in ALGORITHMS:
        path = root / algorithm["path"]
        raw = path.read_bytes()
        source = raw.decode("utf-8")
        tree = ast.parse(source, filename=algorithm["path"])
        functions = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        if algorithm["function"] not in functions:
            raise ValueError(f"algorithm_function_missing:{algorithm['function']}")
        missing = [anchor for anchor in algorithm["anchors"] if anchor not in source]
        if missing:
            raise ValueError(f"algorithm_source_anchor_missing:{algorithm['id']}")
        hashes[algorithm["path"]] = hashlib.sha256(raw).hexdigest()
        rows.append(
            {
                "id": algorithm["id"],
                "source_path": algorithm["path"],
                "function": algorithm["function"],
                "source_anchors": algorithm["anchors"],
                "pseudocode": algorithm["pseudocode"],
            }
        )
    return {
        "schema_version": "source_bound_algorithm_reference_v1",
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip(),
        "source_sha256": hashes,
        "algorithms": rows,
        "graph_diagram_mermaid": DIAGRAM,
        "invariant_diagram_mermaid": INVARIANT_DIAGRAM,
        "limitations": [
            "Pseudocode summarizes source functions and is not executable code.",
            "Anchors prove the named guards/branches are present, not formal verification or clinical validity.",
            "This graph records provenance and consistency; it does not establish truth of source statements.",
        ],
    }


def render(value):
    lines = [
        "# Source-bound algorithm reference",
        "",
        f"**Source commit:** `{value['source_commit']}`",
        "",
        "Source files are SHA-256 bound below. Pseudocode was checked against actual function definitions and guard anchors; it is a summary, not executable code or proof of clinical correctness.",
        "",
    ]
    for algorithm in value["algorithms"]:
        lines += [
            f"## {algorithm['id']}",
            "",
            f"Implementation: `{algorithm['source_path']}::{algorithm['function']}`",
            "",
        ]
        lines.extend(
            f"{index}. {step}" for index, step in enumerate(algorithm["pseudocode"], 1)
        )
        lines += ["", "Source guards:", ""]
        lines.extend(f"- `{anchor}`" for anchor in algorithm["source_anchors"])
        lines.append("")
    lines += [
        "## Evidence graph",
        "",
        "```mermaid",
        value["graph_diagram_mermaid"],
        "```",
        "",
        "## Directed graph invariants",
        "",
        "```mermaid",
        value["invariant_diagram_mermaid"],
        "```",
        "",
        "## Source hashes",
        "",
    ]
    lines.extend(
        f"- `{path}`: `{digest}`" for path, digest in value["source_sha256"].items()
    )
    lines += ["", "## Limitations", ""]
    lines.extend(f"- {item}" for item in value["limitations"])
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", default="evaluation/architecture/algorithm-reference-v1.json"
    )
    args = parser.parse_args()
    output = Path(args.output)
    value = build(".")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")
    output.with_suffix(".md").write_text(render(value), encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "output": output.as_posix(),
                "algorithms": len(value["algorithms"]),
                "status": "written",
            }
        )
    )


if __name__ == "__main__":
    main()
