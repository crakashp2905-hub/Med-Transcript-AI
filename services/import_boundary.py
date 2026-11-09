"""Static evaluation import boundary checks."""

FORBIDDEN_EVALUATION_IMPORTS = (
    'services.api.storage', 'services.api.routers', 'services.asr.worker',
)


def validate_evaluation_imports(imports):
    violations = sorted(set(imports) & set(FORBIDDEN_EVALUATION_IMPORTS))
    if violations:
        raise ValueError('evaluation_import_boundary:' + ','.join(violations))
    return True
