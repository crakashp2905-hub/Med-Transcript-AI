"""Speaker-turn duration and clustering diagnostics."""


def diagnose(segments, *, min_duration_ms=300, max_expected_clusters=4):
    if min_duration_ms <= 0 or max_expected_clusters < 1:
        raise ValueError('invalid_diagnostic_limits')
    short = [i for i, row in enumerate(segments) if row['end_ms'] - row['start_ms'] < min_duration_ms]
    boundaries = [i for i in range(1, len(segments)) if segments[i]['speaker_id'] != segments[i-1]['speaker_id']]
    clusters = len({row.get('speaker_id') for row in segments})
    return {'short_turns': short, 'speaker_change_boundaries': boundaries,
            'cluster_count': clusters, 'cluster_status': 'unresolved_high_cluster_count' if clusters > max_expected_clusters else 'within_declared_limit',
            'false_split_candidates': short, 'requires_review': bool(short or clusters > max_expected_clusters)}
