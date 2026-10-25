"""Exact, bounded fact-level version comparison for authorized immutable notes."""


def compare(before,after):
    left={f['fact_id']:f for f in before['facts']}
    right={f['fact_id']:f for f in after['facts']}
    fields=('text','section','category','subject','assertion','temporality','origin','evidence',
        'excluded','clarification','reviewed','critical_reviewed','concept','anatomical_site','laterality','clinical_source',
        'medication_name','dose_value','dose_unit','route','frequency','duration','allergen','allergy_reaction')
    rows=[]
    for fid in dict.fromkeys([*left,*right]):
        a,b=left.get(fid),right.get(fid)
        changed=[k for k in fields if (a or {}).get(k)!=(b or {}).get(k)]
        if a and b and not changed:
            continue
        rows.append({'fact_id':fid,'change':'added' if a is None else 'removed' if b is None else 'changed',
            'changed_fields':changed,'before':{k:a.get(k) for k in fields} if a else None,
            'after':{k:b.get(k) for k in fields} if b else None})
    return {'before_note':before['id'],'after_note':after['id'],
        'source_changed':before['transcript_version_id']!=after['transcript_version_id'],
        'changes':rows,'unchanged_facts':sum(fid in right and not any(left[fid].get(k)!=right[fid].get(k) for k in fields) for fid in left),
        'comparison_version':'exact_fact_fields_v1'}
