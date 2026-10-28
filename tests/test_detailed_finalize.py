from copy import deepcopy
import json
import os
from pathlib import Path
import pytest

from services.detailed_finalize import draft_summary,process_alive


def test_saved_draft_screen_summary_checks_outputs_instead_of_trusting_scalar_claims(tmp_path):
    fact={'fact_id':'one','section':'plan','text':'Continue warfarin 0.5 mg daily.'}
    row={'id':'case','exact_preservation':True,'output':{'draft':{'statements':[{'section':'plan','text':fact['text'],'fact_ids':['one']}]}}}
    report={'complete':True,'cases':[{'id':'case','facts':[fact]}],'deterministic':[row],
        'models':[{'model':'local','runs':[{'id':'case','failed':True,'exact_preservation':False}]}]}
    path=tmp_path/'draft.json';path.write_text(json.dumps(report));value=draft_summary(path)
    assert value['rows'][0]['exact_preservation_cases']==1 and value['rows'][1]['failed_cases']==1
    assert value['clinician_correction_time_measured'] is False
    changed=deepcopy(report);changed['deterministic'][0]['output']['draft']['statements'][0]['text']='Continue warfarin 5 mg daily.'
    path.write_text(json.dumps(changed))
    with pytest.raises(ValueError):draft_summary(path)


def test_owned_process_liveness_probe_is_read_only():
    assert process_alive(os.getpid())
