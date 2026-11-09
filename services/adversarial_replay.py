"""Replay guard for approved notes after source or model changes."""

from hashlib import sha256


def fingerprint(text):
    return sha256(text.encode('utf-8')).hexdigest()


def replay(*, approved_note, approved_source_hash, approved_model_digest,
           current_source_hash, current_model_digest, regenerated_note):
    source_changed = approved_source_hash != current_source_hash
    model_changed = approved_model_digest != current_model_digest
    note_changed = approved_note != regenerated_note
    return {
        'source_changed': source_changed,
        'model_changed': model_changed,
        'note_changed': note_changed,
        'approval_stale': source_changed or model_changed or note_changed,
        'publication_allowed': False,
    }
