"""No-text operational and independently annotated note evaluation statistics."""
import math
from services.evaluation import tokens
from services.clinical_metrics import character_distance


def summarize_runs(rows):
    if not rows:
        raise ValueError("Measured runs required")
    times = sorted(r["wall_seconds"] for r in rows)
    if any(not isinstance(t,(int,float)) or isinstance(t,bool) or not math.isfinite(t) or t<0 for t in times):
        raise ValueError("Invalid measured latency")
    costs = [r.get("cost") for r in rows]
    costs_known = all(type(x) in (int,float) and math.isfinite(x) and x>=0 for x in costs)
    return {"count":len(rows),"p50_seconds":times[math.ceil(.5*len(times))-1],
        "p95_seconds":times[math.ceil(.95*len(times))-1],
        "cost_total":sum(costs) if costs_known else None,
        "cost_status":"measured" if costs_known else "not_measured",
        "failures":sum(r.get("failed",False) for r in rows)}


def correction(before, after, wall_ms, active_ms=None):
    if wall_ms<0 or active_ms is not None and not 0<=active_ms<=wall_ms:
        raise ValueError("Review duration outside observed wall time")
    return {"word_edits":character_distance(tokens(before),tokens(after)),"review_wall_ms":wall_ms,
        "self_reported_active_ms":active_ms,"active_time_verified":False,
        "raw_text_in_telemetry":False}


def note_correction(before,after,wall_ms,active_ms=None):
    def text(note):
        return ' '.join(s['text'] for sec in note['sections'] for s in sec['statements'])
    result=correction(text(before),text(after),wall_ms,active_ms)
    left={f['fact_id']:f for f in before['facts']};right={f['fact_id']:f for f in after['facts']}
    fields=('text','category','section','subject','assertion','temporality','excluded','concept','anatomical_site',
        'laterality','clinical_source','medication_name','dose_value','dose_unit','route','frequency','duration','allergen','allergy_reaction')
    result.update(facts_added=len(right.keys()-left.keys()),facts_removed=len(left.keys()-right.keys()),
        field_edit_counts={k:sum(left[f].get(k)!=right[f].get(k) for f in left.keys()&right.keys()) for k in fields})
    return result
