import {useState} from 'react';
import type {Fact} from './facts';
export function ClinicalBatch({facts,current,disabled,load}:{facts:Fact[];current:Fact[];disabled:boolean;load:(facts:Fact[])=>void}){
 const [selected,setSelected]=useState<Set<string>>(new Set());
 const key=(f:Fact)=>f.evidence?`${f.evidence.segment_id}:${f.evidence.start_char}:${f.evidence.end_char}`:`id:${f.fact_id}`;
 const existing=new Set(current.map(key)),chosen=facts.filter(f=>selected.has(f.fact_id)),fresh=chosen.filter(f=>!existing.has(key(f)));
 const unreviewed=(items:Fact[])=>items.map(f=>({...f,reviewed:false,critical_reviewed:false}));
 return <section aria-label="Select source-linked clinical proposals"><details><summary>Review {facts.length} source-span proposals in this batch</summary><p>Select relevant statements for the note. Unselected spans remain in the saved proposal; selection does not attest completeness or clinical accuracy.</p>{facts.map(f=><label className="check" key={f.fact_id}><input type="checkbox" checked={selected.has(f.fact_id)} disabled={disabled} onChange={event=>setSelected(old=>{const next=new Set(old);if(event.target.checked)next.add(f.fact_id);else next.delete(f.fact_id);return next;})}/><span>{f.text}<small>{f.category} · {f.subject} · {f.assertion}</small></span></label>)}</details><p>{chosen.length} selected; {fresh.length} new source spans. Note editor limit: 300 facts.</p><button disabled={disabled||!fresh.length||current.length+fresh.length>300} onClick={()=>load([...current,...unreviewed(fresh)])}>Add selected unreviewed proposals</button><button disabled={disabled||!chosen.length||chosen.length>300} onClick={()=>load(unreviewed(chosen))}>Replace editor with selected unreviewed proposals</button></section>;
}
