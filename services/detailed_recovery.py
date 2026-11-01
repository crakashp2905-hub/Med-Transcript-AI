"""Bounded, serial recovery of stopped development experiments; originals stay immutable."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from services.api.ingest import file_sha256
from services.evidence_io import atomic_json
from services.inference_slot import local_inference_slot

SUITE = Path('evaluation/detailed-recovery-v3.json')
ROOT = Path('evaluation/runs/meddistract-recovery-v3')
RECEIPT = Path('evaluation/reports/detailed-recovery-v3.json')
MODES = ('speech_aware', 'context')
CANDIDATE = 'faster-whisper-large-v3'


def initialize():
    if SUITE.exists():
        raise FileExistsError('Preserve existing recovery protocol')
    suite = json.loads(Path('evaluation/detailed-suite-v2.json').read_text())
    suite['schema_version'] = 'detailed_recovery_v3'
    suite['recovery_note'] = 'Reuse verified completed recordings only; unfinished recordings rerun in full. Original timings are retained, not a fresh full-corpus latency measurement.'
    suite['timeout_per_candidate_seconds'] = 8 * 3600
    suite['recovery_modes'] = list(MODES)
    job = next(j for j in suite['jobs'] if j['candidate_id'] == CANDIDATE)
    job['resume_by_mode'] = {}
    for mode in MODES:
        path = Path(f'evaluation/runs/meddistract-detailed-v2/{CANDIDATE}.{mode}.json')
        report = json.loads(path.read_text(encoding='utf-8'))
        if report['complete'] or not report['cases']:
            raise ValueError('Expected a preserved partial experiment')
        job['resume_by_mode'][mode] = {'path': path.as_posix(), 'sha256': file_sha256(path)}
    suite['source_text_sha256'] = {name: hashlib.sha256(Path(name).read_text(encoding='utf-8').encode('utf-8')).hexdigest()
                                 for name in [*suite['source_text_sha256'], 'services/detailed_recovery.py']}
    atomic_json(SUITE, suite)
    return suite


def publish(paths, message):
    subprocess.run(['git', 'add', '--', *paths], check=True)
    changed = subprocess.run(['git', 'diff', '--cached', '--quiet', '--', *paths])
    if changed.returncode not in (0, 1):
        changed.check_returncode()
    if changed.returncode == 1:
        subprocess.run(['git', 'commit', '--only', '-m', message, '--', *paths], check=True)
    subprocess.run(['git', 'push', 'origin', 'main'], check=True)


def run(do_publish=False):
    suite = json.loads(SUITE.read_text())
    for name, digest in suite['source_text_sha256'].items():
        if hashlib.sha256(Path(name).read_text(encoding='utf-8').encode('utf-8')).hexdigest() != digest:
            raise ValueError('Frozen recovery source changed')
    ROOT.mkdir(parents=True, exist_ok=True)
    # A second launch must never truncate an existing attempt.
    if RECEIPT.exists() or any(ROOT.glob('*.json')):
        raise FileExistsError('Preserve previous recovery; choose a new version')
    receipt = {'schema_version': 'detailed_recovery_v3', 'suite_sha256': file_sha256(SUITE),
               'complete': False, 'maximum_normalized_wer': .05, 'model_promoted': None,
               'clinical_acceptance': False, 'paid_calls': 0, 'experiments': []}
    atomic_json(RECEIPT, receipt)
    for mode in MODES:
        output = ROOT / f'{CANDIDATE}.{mode}.json'
        state = {'mode': mode, 'status': 'waiting_for_inference_slot', 'report': output.as_posix()}
        receipt['experiments'].append(state)
        atomic_json(RECEIPT, receipt)
        # Bound both admission and inference; no abandoned child may hold the slot.
        admission_deadline = time.monotonic() + 3600
        while True:
            with local_inference_slot() as acquired:
                if acquired:
                    state['status'] = 'running'; atomic_json(RECEIPT, receipt)
                    with output.with_suffix('.log').open('w', encoding='utf-8') as log:
                        child = subprocess.Popen([sys.executable, '-m', 'services.detailed_benchmark',
                            '--suite', str(SUITE), '--candidate', CANDIDATE, '--mode', mode, '--output', str(output)],
                            stdout=log, stderr=subprocess.STDOUT,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                            start_new_session=os.name != 'nt')
                        try:
                            child.wait(timeout=suite['timeout_per_candidate_seconds'])
                            state['status'] = 'exited' if child.returncode == 0 else 'runtime_failed'
                        except subprocess.TimeoutExpired:
                            if os.name == 'nt':
                                subprocess.run(['taskkill', '/PID', str(child.pid), '/T', '/F'], stdout=log, stderr=subprocess.STDOUT, check=False)
                            else:
                                import signal
                                os.killpg(child.pid, signal.SIGKILL)
                            child.wait(); state['status'] = 'resource_timeout'
                    break
            if time.monotonic() >= admission_deadline:
                state['status'] = 'admission_timeout'; break
            time.sleep(5)
        if output.exists():
            report = json.loads(output.read_text(encoding='utf-8'))
            state.update(complete=report['complete'], completed_cases=len(report['cases']),
                         sha256=file_sha256(output), resumed_from=report.get('resumed_from'),
                         conditions=report.get('conditions') if report['complete'] else None)
            if report['complete']:
                state['status'] = 'complete'
        atomic_json(RECEIPT, receipt)
        if do_publish:
            publish([str(RECEIPT)] + ([str(output)] if output.exists() else []), f'Record preserved experiment recovery: {mode}')
    receipt['complete'] = all(e.get('complete', False) for e in receipt['experiments'])
    atomic_json(RECEIPT, receipt)
    if do_publish:
        publish([str(RECEIPT)], 'Record final recovery completion status without promoting a model')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['init', 'run'])
    parser.add_argument('--publish', action='store_true')
    parser.add_argument('--keep-awake', action='store_true')
    args = parser.parse_args()
    if args.action == 'init':
        initialize()
    else:
        power = None
        if args.keep_awake and os.name == 'nt':
            import ctypes
            power = ctypes.WinDLL('kernel32').SetThreadExecutionState
            power.argtypes = [ctypes.c_uint32]; power.restype = ctypes.c_uint32
            if not power(0x80000001):
                raise OSError('Cannot hold temporary system-awake request')
        try:
            run(args.publish)
        finally:
            if power:
                power(0x80000000)
