"""Generate a dependency SBOM from committed constraints without network access."""
import re
from pathlib import Path


def generate(root='.'):
    path = Path(root) / 'constraints-ci.txt'; components = []
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '==' not in line:
            continue
        name, version = line.split('==', 1)
        if not re.fullmatch(r'[A-Za-z0-9_.-]+', name) or not version:
            raise ValueError('invalid_constraint_component')
        components.append({'name': name, 'version': version, 'source': 'constraints-ci.txt'})
    return {'bomFormat': 'CycloneDX', 'specVersion': '1.5', 'components': components,
            'dependency_source': 'committed_constraints', 'network_access': False,
            'audit_status': 'not_run_without_tooling', 'real_patient_release_authorized': False}
