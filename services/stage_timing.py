"""Failure-inclusive stage timing for synthetic and local workflow evidence."""
from dataclasses import dataclass
import math
import time

STAGES = ('recording','transfer','normalization','asr','diarization','extraction','drafting','verification','clinician_review','export')

@dataclass
class StageTiming:
    status: str = 'not_started'
    wall_seconds: float | None = None
    error_code: str | None = None

class StageTimer:
    def __init__(self):
        self.stages = {stage: StageTiming() for stage in STAGES}
    def measure(self, stage, operation):
        if stage not in self.stages: raise ValueError('unknown_timing_stage')
        started = time.perf_counter(); self.stages[stage] = StageTiming(status='running')
        try:
            value = operation()
        except Exception as exc:
            elapsed = time.perf_counter() - started
            self.stages[stage] = StageTiming(status='failed', wall_seconds=elapsed, error_code=type(exc).__name__)
            raise
        elapsed = time.perf_counter() - started
        if not math.isfinite(elapsed) or elapsed < 0: raise ValueError('invalid_stage_timing')
        self.stages[stage] = StageTiming(status='succeeded', wall_seconds=elapsed)
        return value
    def mark_unavailable(self, stage, error_code):
        if stage not in self.stages: raise ValueError('unknown_timing_stage')
        if not error_code or not isinstance(error_code, str): raise ValueError('timing_error_code_required')
        self.stages[stage] = StageTiming(status='unavailable', error_code=error_code)
    def report(self):
        return {'schema_version':'stage_timing_v1','stages':{name:{'status':value.status,'wall_seconds':value.wall_seconds,'error_code':value.error_code} for name,value in self.stages.items()},
                'complete':all(value.status == 'succeeded' for value in self.stages.values()),
                'limitations':'Timing records software wall time only; it does not establish clinical performance or hardware equivalence.'}
