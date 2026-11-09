"""Provenance labels for optimization and reproducible adversarial data."""


def classify(source, *, predeclared=False, synthetic_oracle=False):
    if predeclared and synthetic_oracle:
        raise ValueError('ambiguous_data_provenance')
    if predeclared:
        kind = 'predeclared_development'
    elif synthetic_oracle:
        kind = 'developer_synthetic_oracle'
    else:
        kind = 'unclassified'
    return {'source': source, 'kind': kind, 'optimization_allowed': kind == 'predeclared_development'}
