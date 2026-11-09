import pytest

from services.import_boundary import validate_evaluation_imports


def test_evaluation_import_boundary_allows_pure_helpers():
    assert validate_evaluation_imports(['services.benchmark_ranking', 'services.canonical']) is True


def test_evaluation_import_boundary_rejects_mutation_modules():
    with pytest.raises(ValueError, match='evaluation_import_boundary'):
        validate_evaluation_imports(['services.api.storage'])
