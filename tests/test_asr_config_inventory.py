from services.asr.config_inventory import inventory


class Profile:
    profile_id = 'missing'
    sha256 = 'digest'

    def availability(self):
        return {'status': 'unavailable', 'reason_code': 'model_unavailable', 'automatic_download': False}


def test_missing_local_weights_remain_unable_to_run():
    result = inventory([Profile()])
    assert result['profiles'][0]['status'] == 'unable_to_run'
    assert result['weights_downloaded'] is False
