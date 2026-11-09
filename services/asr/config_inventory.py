"""Inventory every declared local ASR profile without downloading weights."""


def inventory(profiles):
    rows = []
    for profile in profiles:
        availability = profile.availability()
        rows.append({'profile_id': profile.profile_id, 'profile_sha256': profile.sha256,
                     'status': 'unable_to_run' if availability['status'] != 'available_not_admitted' else 'available_not_admitted',
                     'availability': availability, 'automatic_download': False})
    return {'profiles': rows, 'count': len(rows), 'weights_downloaded': False}
