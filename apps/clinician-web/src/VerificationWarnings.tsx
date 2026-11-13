import type {Finding,Segment} from './workspaceTypes';
import type {Fact} from './facts';
const title=(value:string)=>value.replaceAll('_',' ').replace(/^./,char=>char.toUpperCase());
export function VerificationWarnings({findings,review,playSource,facts=[],sourceSegments=[],validatorVersion,sourceVersionId}:{findings:Finding[];review:(id:string|null)=>void;playSource?:(segmentId:string)=>void;facts?:Fact[];sourceSegments?:Segment[];validatorVersion?:string;sourceVersionId?:string}){
 const groups=['critical','major','minor','info'];
 const group=(severity:string)=>groups.includes(severity)?severity:severity==='warning'?'minor':'major';
 return <div className="verification-groups"><p className="muted">Review order uses deterministic finding severity and evidence availability. These are review priorities, not calibrated confidence probabilities.</p>{groups.map(severity=>{
  const items=findings.filter(item=>group(item.severity)===severity);
  return items.length?<section key={severity} aria-label={`${severity} verification issues`}><h3>{title(severity)} <span className="count">{items.length}</span></h3>{items.map(item=>{
   const fact=facts.find(f=>f.fact_id===item.fact_id),reference=item.source_reference;
   const sourceMatches=!!reference&&reference.transcript_version_id===sourceVersionId;
   const segment=sourceSegments.find(row=>row.segment_id===reference?.segment_id);
   const excerpt=sourceMatches&&segment&&reference&&segment.text.slice(reference.start_char,reference.end_char);
   return <div className="finding" key={item.finding_id}><span className={`severity ${severity}`}>{item.severity}</span><h4>{title(item.code)}</h4><p>{item.message}</p>
   {severity==='critical'&&<details><summary>Evidence and check details</summary>
    {excerpt?<blockquote>{excerpt}</blockquote>:sourceMatches&&fact?.evidence?<blockquote>{fact.evidence.quote}</blockquote>:<p>{fact?.origin==='clinician_entered'?'Clinician addition has no source citation.':'Review the complete saved source context.'}</p>}
    {fact&&<p>Saved statement: {fact.text}</p>}
    <p>Fields: {(item.mismatch_fields||['statement_text']).map(title).join(', ')}</p>
    <small>Validator: {item.validator_version||validatorVersion||'legacy version not recorded'}</small>
    {excerpt&&playSource&&<button onClick={()=>playSource(segment!.segment_id)}>Play source excerpt</button>}
   </details>}
   {item.fact_id&&<button onClick={()=>review(item.fact_id)}>Review statement and source</button>}</div>;
  })}</section>:null;
 })}</div>;
}
