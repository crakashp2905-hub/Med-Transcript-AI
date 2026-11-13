import pytest

from fastapi import HTTPException

from services.review.clinical_models import ClinicalModelFailure
from services.review.clinical_routes import (
    clinical_provider_http_error,
    semantic_provider_http_error,
)


@pytest.mark.parametrize(
    "failure_code",
    [
        "model_digest_mismatch",
        "clinical_model_timeout",
        "clinical_model_transport_failure",
        "invalid_clinical_model_schema",
    ],
)
def test_unavailable_or_unsupported_extraction_output_is_not_empty_success(
    failure_code,
):
    error = clinical_provider_http_error(ClinicalModelFailure(failure_code))

    assert isinstance(error, HTTPException)
    assert error.status_code == 503
    assert error.detail == "clinical_model_unavailable"


def test_unavailable_verifier_output_is_not_empty_success():
    error = semantic_provider_http_error(ClinicalModelFailure("clinical_model_timeout"))

    assert error.status_code == 503
    assert error.detail == "clinical_model_unavailable"


def test_unexpected_invalid_request_remains_a_client_error():
    error = clinical_provider_http_error(ValueError("invalid source"))

    assert error.status_code == 422
    assert error.detail == "clinical_extraction_failed_no_output_admitted"
