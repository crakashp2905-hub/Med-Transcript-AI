import React,{useRef,useState} from 'react';
import type {Fact} from './facts';

type Extraction={id:string;facts:Fact[];findings?:{code:string}[];source_span_fallback_count?:number;source_relationships?:{relations:{subject:string;entities:string[];quantities:[string,string][];timing:string[];routes:string[];actions:string[];condition:string;assertion:string;evidence:{quote:string}}[]}};
type Check={fact_id:string;label:string;reason:string;requires_review:boolean;rule_findings:{code:string}[]};
type Request=(path:string,options?:RequestInit)=>Promise<any>;

export function ClinicalProposals({encounter,transcript,note,disabled,request,loadFacts}:{encounter:string;transcript:string;note:{id:string;facts:Fact[]}|null;disabled:boolean;request:Request;loadFacts:(facts:Fact[])=>void}){
 const [extraction,setExtraction]=useState<Extraction|null>(null),[checks,setChecks]=useState<Check[]>([]),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const inflight=useRef(false);
 const eligible=note?.facts.filter(f=>f.evidence&&!f.excluded)||[];
 const next=eligible.filter(f=>!checks.some(c=>c.fact_id===f.fact_id)).slice(0,20);
 async function run(kind:'extract'|'verify'){if(inflight.current)return;inflight.current=true;setBusy(true);setError('');try{
  if(kind==='extract')setExtraction(await request(`/v1/encounters/${encounter}/fact-proposals`,{method:'POST',body:JSON.stringify({transcript_version_id:transcript,mode:'local_model'})}));
  else {const r=await request(`/v1/encounters/${encounter}/semantic-checks`,{method:'POST',body:JSON.stringify({note_version_id:note!.id,fact_ids:next.map(f=>f.fact_id)})});setChecks(c=>[...c,...r.verdicts]);}
 }catch(e){setError(e instanceof Error?e.message:'The local clinical model request failed.');}finally{setBusy(false);inflight.current=false;}}
 return <section className="panel"><div className="panel-heading"><h2>Local clinical model proposals</h2></div>
 <p>Optional, unvalidated model assistance. Extracted facts remain unreviewed. A second model checks saved claims independently; its verdicts never clear approval findings.</p>
 <button disabled={disabled||busy} onClick={()=>void run('extract')}>Propose facts with local model</button>
 <button disabled={disabled||busy||!note||!next.length} onClick={()=>void run('verify')}>Check {next.length} saved claims with independent model</button>
 {busy&&<p role="status">Running local model; bounded to one request and a 60-second timeout.</p>}
 {error&&<p role="alert" className="error">{error}</p>}
 {extraction&&<><p>{extraction.facts.length} unreviewed facts proposed. {extraction.findings?.length||0} coverage findings.</p>{!!extraction.source_span_fallback_count&&<p className="callout">The model omitted {extraction.source_span_fallback_count} source spans. The deterministic baseline retained them for your review.</p>}{extraction.source_relationships&&<details><summary>{extraction.source_relationships.relations.length} evidence-linked relationship proposals · unreviewed</summary><p>Limited explicit rules; these bindings do not establish clinical meaning. Review attribution, timing and scope against the source.</p>{extraction.source_relationships.relations.map((r,i)=><article key={i}><blockquote>{r.evidence.quote}</blockquote><p>{r.subject} · {r.assertion} · {r.entities.join(', ')}</p><p>{[...r.quantities.map(q=>`${q[1]} ${q[0]}`),...r.timing,...r.routes,...r.actions,r.condition?`if ${r.condition}`:''].filter(Boolean).join(' · ')}</p></article>)}</details>}<button disabled={disabled||busy||!extraction.facts.length} onClick={()=>loadFacts(extraction.facts.map(f=>({...f,reviewed:false,critical_reviewed:false})))}>Replace editor with these unreviewed proposals</button></>}
 {checks.length>0&&<><p>{checks.length} of {eligible.length} evidence-linked saved facts checked. Unchecked facts remain unevaluated.</p>{checks.map(c=><details key={c.fact_id}><summary>{c.label}{c.requires_review?' · Review required':''}</summary><p>{eligible.find(f=>f.fact_id===c.fact_id)?.text}</p><p>{c.reason}</p><p>{c.rule_findings.map(f=>f.code.replaceAll('_',' ')).join('; ')}</p></details>)}</>}
 </section>;
}
