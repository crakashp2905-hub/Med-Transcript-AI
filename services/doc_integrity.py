"""Read-only Markdown link and current-release-claim checks."""
import re
from pathlib import Path


LINK = re.compile(r'\[[^\]]+\]\(([^)]+)\)')


def scan(root='.'):
    root = Path(root).resolve(); results = []
    for path in sorted([root / 'README.md', *((root / 'docs').rglob('*.md'))]):
        if not path.is_file():
            continue
        text = path.read_text(encoding='utf-8', errors='replace')
        for target in LINK.findall(text):
            target = target.split('#', 1)[0]
            if not target or target.startswith(('http://', 'https://', 'mailto:')):
                continue
            resolved = (path.parent / target).resolve()
            results.append({'source': path.relative_to(root).as_posix(), 'target': target,
                            'status': 'pass' if resolved.is_file() or resolved.is_dir() else 'missing'})
    readme = (root / 'README.md').read_text(encoding='utf-8', errors='replace')
    claims = {'wer_gate_5_percent': '5%' in readme,
              'clinical_release_blocked': 'Real-patient release is not authorized' in readme,
              'failures_visible': 'remain visible' in readme or 'failures' in readme}
    return {'schema_version': 'doc_integrity_v1', 'links': results,
            'broken_links': [r for r in results if r['status'] != 'pass'],
            'claims': claims, 'status': 'pass' if all(claims.values()) and not any(r['status'] != 'pass' for r in results) else 'fail',
            'limitations': 'Local relative links and headline release claims only; external URLs are not fetched.'}


if __name__ == '__main__':
    import argparse, json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    report = scan()
    Path(args.out).write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': report['status'], 'links': len(report['links']), 'broken': len(report['broken_links'])}))
