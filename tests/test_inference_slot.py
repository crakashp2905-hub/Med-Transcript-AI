import os
import subprocess
import sys
from services.inference_slot import local_inference_slot


def test_second_process_cannot_admit_inference_until_slot_is_released(tmp_path,monkeypatch):
    path=str(tmp_path/'admission.lock');monkeypatch.setenv('MED_TRANSCRIPT_INFERENCE_LOCK',path)
    command=[sys.executable,'-c',"from services.inference_slot import local_inference_slot; c=local_inference_slot(); print(c.__enter__()); c.__exit__(None,None,None)"]
    with local_inference_slot() as ready:
        assert ready
        blocked=subprocess.run(command,capture_output=True,text=True,check=True,timeout=15)
        assert blocked.stdout.strip()=='False'
    allowed=subprocess.run(command,capture_output=True,text=True,check=True,timeout=15)
    assert allowed.stdout.strip()=='True'
