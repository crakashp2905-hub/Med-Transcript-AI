"""Mark transcript/user content as untrusted prompt data."""


def wrap(text):
    if not isinstance(text, str):
        raise ValueError('untrusted_text_required')
    return {'content': text, 'trust': 'untrusted_data', 'instructions_executable': False,
            'markup_interpreted': False}
