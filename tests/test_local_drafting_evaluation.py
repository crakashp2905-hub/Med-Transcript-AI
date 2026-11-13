import json
from copy import deepcopy

from services import local_drafting_evaluation as evaluation
from services.review.providers import DeterministicProvider


def test_drafting_benchmark_sends_identical_frozen_facts_to_each_model(
    monkeypatch, tmp_path
):
    from services.review.clinical_models import MODEL_DIGESTS

    seen = {"qwen2.5:1.5b": [], "qwen2.5:7b": []}
    catalog = {
        "models": [
            {
                "name": model,
                "digest": MODEL_DIGESTS[model],
                "details": {"parameter_size": model},
            }
            for model in seen
        ]
    }

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return json.dumps(catalog).encode()

    class FakeProvider:
        def __init__(self, endpoint, model, **kwargs):
            self.model = model

        def draft(self, facts, *, authorized, synthetic):
            seen[self.model].append(deepcopy(facts))
            return DeterministicProvider().draft(
                facts, authorized=authorized, synthetic=synthetic
            )

    monkeypatch.setattr(
        evaluation.urllib.request, "urlopen", lambda *args, **kwargs: Response()
    )
    monkeypatch.setattr(evaluation, "JSONProvider", FakeProvider)
    output = tmp_path / "comparison.json"

    evaluation.run(["qwen2.5:1.5b", "qwen2.5:7b"], str(output), structured=True)
    report = json.loads(output.read_text(encoding="utf-8"))

    assert len(report["deterministic_baseline"]) == len(evaluation.CASES) == 4
    assert len(seen["qwen2.5:1.5b"]) == len(seen["qwen2.5:7b"]) == 4
    assert seen["qwen2.5:1.5b"] == seen["qwen2.5:7b"]
    assert report["fixture_sha256"]
    assert all(model["exact_cases"] == 4 for model in report["models"])
