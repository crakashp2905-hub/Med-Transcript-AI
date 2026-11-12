"""Frozen local prompt-evaluation report contract."""


def report(
    *, prompt_digest, input_digest, outputs, failures=None, acceptance_data_used=False
):
    if not prompt_digest or not input_digest or not isinstance(outputs, list):
        raise ValueError("prompt_report_inputs_required")
    if acceptance_data_used:
        raise ValueError("acceptance_only_data_forbidden")
    return {
        "schema_version": "prompt_eval_v1",
        "prompt_digest": prompt_digest,
        "input_digest": input_digest,
        "outputs": outputs,
        "failures": failures or [],
        "acceptance_data_used": False,
        "json_only": True,
    }
