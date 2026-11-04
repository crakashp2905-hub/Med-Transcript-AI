"""Declared timestamp capability is separate from measured alignment validity."""
from dataclasses import dataclass
from typing import Literal
import math

TimestampKind = Literal['none', 'chunk', 'segment', 'word']


@dataclass(frozen=True)
class TimestampCapability:
    kind: TimestampKind
    native: bool
    word_alignment_validated: bool = False


REGISTRY = {
    'whisper': TimestampCapability('segment', True),
    'omi': TimestampCapability('none', False),
    'parakeet': TimestampCapability('none', False),
    'qwen': TimestampCapability('none', False),
}


def capability(runtime, has_native_segments=False):
    declared = REGISTRY.get(runtime, TimestampCapability('none', False))
    if declared.kind == 'segment' and not has_native_segments:
        return TimestampCapability('chunk', False)
    return declared


def check_segments(segments, duration_ms):
    if not isinstance(duration_ms, (int, float)) or isinstance(duration_ms, bool) or not math.isfinite(duration_ms) or duration_ms <= 0:
        raise ValueError('invalid_audio_duration')
    errors, gaps = [], []
    previous_start = previous_end = 0
    seen = set()
    for index, segment in enumerate(segments):
        start, end = segment['start_ms'], segment['end_ms']
        if (not isinstance(start, (int, float)) or isinstance(start, bool) or not isinstance(end, (int, float)) or isinstance(end, bool)
                or not math.isfinite(start) or not math.isfinite(end)):
            errors.append({'index': index, 'code': 'invalid_timestamp_type'})
            continue
        if not 0 <= start < end <= duration_ms:
            errors.append({'index': index, 'code': 'timestamp_out_of_bounds'})
        if start < previous_start:
            errors.append({'index': index, 'code': 'timestamp_order_reversed'})
        if start < previous_end:
            errors.append({'index': index, 'code': 'timestamp_overlap_requires_review'})
        if start > previous_end:
            gaps.append({'start_ms': previous_end, 'end_ms': start, 'status': 'untranscribed_not_proven_silence'})
        key = (start, end, segment.get('text', ''))
        if key in seen:
            errors.append({'index': index, 'code': 'duplicate_segment'})
        seen.add(key)
        previous_start, previous_end = start, max(previous_end, end)
    if previous_end < duration_ms:
        gaps.append({'start_ms': previous_end, 'end_ms': duration_ms, 'status': 'untranscribed_not_proven_silence'})
    return {'bounds_and_order_valid': not errors, 'issues': errors, 'gaps': gaps,
            'word_alignment_validated': False, 'speaker_roles_validated': False,
            'limitation': 'Bounds checks do not establish word alignment, silence, speaker identity or clinical completeness.'}
