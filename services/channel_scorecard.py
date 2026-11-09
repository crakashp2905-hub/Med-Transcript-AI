"""Configuration scorecard that keeps input count distinct from device equivalence."""


def compare(configurations):
    if not isinstance(configurations, dict) or not configurations:
        raise ValueError('configurations_required')
    rows = []
    for name, value in configurations.items():
        if not isinstance(value, dict) or 'channels' not in value or 'source' not in value:
            raise ValueError(f'invalid_configuration:{name}')
        rows.append({'name': name, 'channels': value['channels'], 'source': value['source'],
                     'hardware_equivalence': value['source'] == 'hardware'})
    return {'configurations': rows, 'hardware_equivalence_claim': False}
