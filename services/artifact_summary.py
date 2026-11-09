"""Render machine-readable artifact results with failures first for humans."""


def summarize(report):
    if not isinstance(report, dict):
        raise ValueError('artifact_report_required')
    failures = []
    for name, value in (report.get('checks') or {}).items():
        status = value.get('status') if isinstance(value, dict) else value
        if status not in ('pass', 'succeeded', 'verified'):
            failures.append({'name': name, 'status': status})
    lines = ['# Artifact summary', '', '## Failures and blocks']
    lines.extend(f"- {item['name']}: {item['status']}" for item in failures) or lines.append('- None recorded')
    lines += ['', '## Checks', *[f"- {name}: {(value.get('status') if isinstance(value, dict) else value)}" for name, value in (report.get('checks') or {}).items()],
              '', 'Clinical release: `BLOCKED_EXTERNAL_EVIDENCE_REQUIRED`.', 'Machine-readable source: versioned JSON receipt.']
    return {'markdown': '\n'.join(lines) + '\n', 'failure_count': len(failures),
            'failures_first': True, 'clinical_release': 'BLOCKED_EXTERNAL_EVIDENCE_REQUIRED',
            'real_patient_release_authorized': False}
