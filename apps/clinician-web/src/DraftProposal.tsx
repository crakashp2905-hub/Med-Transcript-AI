import React,{useState} from 'react';
import {ApiError} from './client/errorCodes';

type Proposal={draft:{statements:{section:string;text:string;fact_ids:string[]}[]};findings:{code:string}[];status:string;provenance?:{provider_mode:string;model?:string};deterministic_baseline?:{draft:{statements:{section:string;text:string;fact_ids:string[]}[]}}};

export function DraftProposal({disabled,generate}:{disabled:boolean;generate:()=>Promise<Proposal>}){
 const [proposal,setProposal]=useState<Proposal|null>(null);
 const [waiting,setWaiting]=useState(false);
 const [error,setError]=useState('');
 async function run(){setWaiting(true);setError('');try{setProposal(await generate());}catch(e){
  const code=e instanceof ApiError?e.code:'';
  const messages:Record<string,string>={
   model_unavailable:'The configured drafting model is unavailable. Nothing was saved. Continue in the manual note editor, or retry after the workspace administrator restores the model.',
   model_integrity_failure:'The configured drafting model failed its integrity check. Nothing was saved. Do not use this model; contact the workspace administrator. You can continue in the manual note editor.',
   draft_proposal_failed_no_output_admitted:'Drafting did not return a valid structured proposal. Nothing was saved. Review the facts and continue in the manual note editor, or retry.',
  };
  setProposal(null);setError(messages[code]||(e instanceof Error?e.message:'Drafting failed. Nothing was saved; review the facts and continue in the manual note editor.'));
 }finally{setWaiting(false);}}
 return <section className="panel"><div className="panel-heading"><h2>Drafting proposal</h2></div>
 <p>Generate a proposal from reviewed facts using the configured provider. Review every statement against its evidence before manually editing the note.</p>
 <button disabled={disabled||waiting} onClick={()=>void run()}>{waiting?'Generating proposal…':'Generate proposal from reviewed facts'}</button>
 {error&&<p role="alert" className="error">{error}</p>}
 {proposal&&<><p className="callout">Unapproved proposal. It has not changed the saved note.</p><div className="scribe-grid"><div><h3>{proposal.provenance?.provider_mode==='local'?`Local model · ${proposal.provenance.model}`:'Configured drafting proposal'}</h3>{proposal.draft.statements.map((s,i)=><p key={i}><strong>{s.section}: </strong>{s.text}<small> · {s.fact_ids.length} cited fact(s)</small></p>)}</div><div><h3>Deterministic baseline</h3>{proposal.deterministic_baseline?.draft.statements.map((s,i)=><p key={i}><strong>{s.section}: </strong>{s.text}</p>)}</div></div>
 {proposal.findings.length>0&&<p role="status">Review findings: {proposal.findings.map(f=>f.code.replaceAll('_',' ')).join('; ')}</p>}</>}
 </section>;
}
