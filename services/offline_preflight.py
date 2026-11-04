"""Read-only local capability inventory. Never installs, downloads or activates accounts."""
import argparse
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import shutil

from services.engineering_status import sha256


def check_baseline(document, root='.', require_local_models=False):
    root = Path(root).resolve()
    checked = 0
    for name, expected in document['benchmark_sha256'].items():
        path = (root/name).resolve()
        if not path.is_relative_to(root) or not path.is_file() or sha256(path) != expected:
            raise ValueError('baseline_evidence_missing_or_changed')
        checked += 1
    missing = []
    for model in document['installed_model_directories']:
        path = (root/model['path']).resolve()
        if not path.is_relative_to(root):
            raise ValueError('baseline_model_directory_missing')
        if not path.is_dir():
            if require_local_models:
                raise ValueError('baseline_model_directory_missing')
            missing.append(model['path'])
    return {'evidence_files_checked': checked, 'model_directories_checked': len(document['installed_model_directories'])-len(missing),
            'missing_local_model_directories': missing, 'model_inference_performed': False}


def inspect(root='.'):
    root = Path(root)
    def present(name):
        try:
            return importlib.util.find_spec(name) is not None
        except (ImportError, ValueError):
            return False
    files = ['pyproject.toml', 'constraints-ci.txt', 'apps/clinician-web/package-lock.json']
    tools = {name: ('available' if present(module) else 'blocked_missing_local_artifact') for name, module in
             [('pytest', 'pytest'), ('codec_av', 'av'), ('coverage', 'coverage'), ('ruff', 'ruff'), ('mypy', 'mypy'), ('pip_audit', 'pip_audit')]}
    wheelhouse = root/'data/wheelhouse'
    return {'schema_version': 'offline_preflight_v1', 'tools': tools,
            'node': 'available' if shutil.which('node') else 'blocked_missing_local_artifact',
            'npm_dependencies': 'available' if (root/'apps/clinician-web/node_modules/typescript').is_dir() else 'blocked_missing_local_artifact',
            'python_wheelhouse': 'available' if list(wheelhouse.glob('*.whl')) else 'blocked_missing_local_artifact',
            'models': [{'path': p.relative_to(root).as_posix(), 'status': 'directory_present_not_a_weight_verification'} for p in sorted((root/'data/models').glob('*')) if p.is_dir()],
            'packages': sorted([{'name': d.metadata['Name'], 'version': d.version} for d in importlib.metadata.distributions()], key=lambda d: d['name'].lower()),
            'config_sha256': {name: sha256(root/name) for name in files if (root/name).is_file()},
            'new_installations_attempted': 0, 'external_calls_attempted': 0,
            'independent_clinical_gold': False, 'real_patient_release_authorized': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    with Path(args.out).open('x', encoding='utf-8') as output:
        json.dump(inspect(), output, indent=2)
