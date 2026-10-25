import React from 'react';
import type {Fact,ClinicalField} from './facts';

export function ClinicalFields({fact,disabled,update}:{fact:Fact;disabled:boolean;update:(value:Partial<Fact>)=>void}){
 const fields:ClinicalField[]=fact.category==='allergy'?['allergen','allergy_reaction']:
  fact.category==='medication'?['medication_name','dose_value','dose_unit','route','frequency','duration']:['concept','anatomical_site'];
 return <details><summary>Structured clinical details</summary><p className="muted">Copy explicit source details. Leave absent information blank; changing a field requires review again.</p>
 <div className="fact-fields">{fields.map(field=><label key={field}>{field.replaceAll('_',' ')}<input disabled={disabled} value={fact[field]||''} maxLength={field==='allergy_reaction'?300:field==='dose_unit'?50:field==='dose_value'||field==='route'||field==='frequency'||field==='duration'?100:field==='concept'?300:200} onChange={e=>update({[field]:e.target.value||null,reviewed:false,critical_reviewed:false})}/></label>)}
 <label>Laterality<select disabled={disabled} value={fact.laterality||'unknown'} onChange={e=>update({laterality:e.target.value,reviewed:false,critical_reviewed:false})}>{['unknown','left','right','bilateral'].map(s=><option key={s}>{s}</option>)}</select></label>
 <label>Clinical source<select disabled={disabled} value={fact.clinical_source||'unknown'} onChange={e=>update({clinical_source:e.target.value,reviewed:false,critical_reviewed:false})}>{['unknown','patient_report','clinician_statement'].map(s=><option key={s}>{s}</option>)}</select></label></div></details>;
}
