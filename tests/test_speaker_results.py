from services.speaker_results import ChannelAssignmentResult, RoleIdentificationResult, SpeakerClusteringResult


def test_speaker_results_keep_clustering_roles_and_channels_independent():
    clustering = SpeakerClusteringResult(({'speaker_id': 'speaker_0'},))
    roles = RoleIdentificationResult(({'speaker_id': 'speaker_0', 'role': 'unknown'},))
    channels = ChannelAssignmentResult(({'speaker_id': 'speaker_0', 'channel': 0},))
    assert clustering.segments[0]['speaker_id'] == roles.assignments[0]['speaker_id'] == channels.channels[0]['speaker_id']
    assert roles.status == 'clinician_confirmation_required'
