"""Recompute development ASR evidence and enumerate unfulfilled clinical release gates."""
import argparse
import hashlib
import json
from pathlib import Path

from services.benchmark_ranking import rank


def assess(root):
    root = Path(root)
    dataset = root / 'evaluation/datasets/primock57-expanded-v1'
    ledger = json.loads((root / 'evaluation/expanded-extension-ledger-v2.json').read_text(encoding='utf-8'))
    ranking = rank(dataset/'manifest.json', dataset/'lock.json', ledger['candidates'], root)
    eligible = [r for r in ranking['ranked'] if r['wer_gate']['status'] == 'pass']
    paths = ['evaluation/expanded-extension-ledger-v2.json',
             'evaluation/datasets/primock57-expanded-v1/manifest.json',
             'evaluation/datasets/primock57-expanded-v1/lock.json']
    paths.extend(r['report'] for r in ranking['ranked'])
    return {'schema_version': 'release_readiness_v1',
            'scope': 'development_evidence_inventory_not_deployment_authorization',
            'maximum_normalized_wer': .05,
            'evaluated_candidates': len(ranking['ranked']),
            'unranked_candidates': len(ranking['unranked']),
            'eligible_development_candidates': [r['candidate_id'] for r in eligible],
            'best_development_candidate': ranking['ranked'][0]['candidate_id'] if ranking['ranked'] else None,
            'best_development_normalized_wer': ranking['ranked'][0]['normalized_wer'] if ranking['ranked'] else None,
            'evidence_sha256': {p: hashlib.sha256((root/p).read_bytes()).hexdigest() for p in paths},
            'gates': [
                {'id': 'development_asr_wer', 'status': 'pass' if eligible else 'fail'},
                *[{'id': name, 'status': 'not_established'} for name in (
                    'independent_acceptance_cohort', 'timestamped_application_asr',
                    'speaker_attribution_quality', 'clinical_extraction_and_verifier_calibration',
                    'credential_verified_clinician_adjudication', 'paired_clinician_study',
                    'institutional_sso_mfa', 'deployment_encryption_and_key_management',
                    'approved_retention_and_backup_deletion', 'external_audit_and_security_review',
                    'institutional_real_patient_pilot_approval')]],
            'production_model_selected': None, 'real_patient_release_authorized': False,
            'note': 'Passing development WER cannot establish the other gates. No operator checkbox or model opinion promotes a clinical release.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='.')
    parser.add_argument('--out', required=True)
    parser.add_argument('--check-release', action='store_true', help='Exit 2 when clinical release is unestablished')
    args = parser.parse_args()
    result = assess(args.root)
    with Path(args.out).open('x', encoding='utf-8') as output:
        json.dump(result, output, indent=2, allow_nan=False)
    if args.check_release and not result['real_patient_release_authorized']:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
