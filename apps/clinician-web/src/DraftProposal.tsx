import React,{useState} from 'react';

type Proposal={draft:{statements:{section:string;text:string;fact_ids:string[]}[]};findings:{code:string}[];status:string};

export function DraftProposal({disabled,generate}:{disabled:boolean;generate:()=>Promise<Proposal>}){
 const [proposal,setProposal]=useState<Proposal|null>(null);
 const [waiting,setWaiting]=useState(false);
 const [error,setError]=useState('');
 async function run(){setWaiting(true);setError('');try{setProposal(await generate());}catch(e){setError(e instanceof Error?e.message:'Drafting failed.');}finally{setWaiting(false);}}
 return <section className="panel"><div className="panel-heading"><h2>Drafting proposal</h2></div>
 <p>Generate a proposal from reviewed facts using the configured provider. Review every statement against its evidence before manually editing the note.</p>
 <button disabled={disabled||waiting} onClick={()=>void run()}>{waiting?'Generating proposal…':'Generate proposal from reviewed facts'}</button>
 {error&&<p role="alert" className="error">{error}</p>}
 {proposal&&<><p className="callout">Unapproved proposal. It has not changed the saved note.</p>{proposal.draft.statements.map((s,i)=><p key={i}><strong>{s.section}: </strong>{s.text}</p>)}
 {proposal.findings.length>0&&<p role="status">Review findings: {proposal.findings.map(f=>f.code.replaceAll('_',' ')).join('; ')}</p>}</>}
 </section>;
}
