from services.algorithm_reference import build, render


def test_algorithm_reference_binds_function_names_guards_and_invariant_diagrams():
    result = build(".")
    assert result["source_commit"]
    assert len(result["source_sha256"]) == 2
    assert all(len(value) == 64 for value in result["source_sha256"].values())
    assert {row["function"] for row in result["algorithms"]} == {
        "validate_proposal",
        "validate_graph_invariants",
        "validate_approved_export",
        "directional_coverage",
    }
    assert all(row["source_anchors"] for row in result["algorithms"])
    assert "Kahn's indegree queue traversal" in " ".join(
        next(
            row
            for row in result["algorithms"]
            if row["id"] == "directed_graph_invariants"
        )["pseudocode"]
    )
    document = render(result)
    assert "```mermaid" in document
    assert "evidence_graph_cycle_detected" in document
    assert "cross-tenant" in document
    assert "clinical validity" in document
