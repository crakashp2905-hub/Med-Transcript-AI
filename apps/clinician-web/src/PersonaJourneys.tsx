import {useState} from 'react';

const journeys={
 general_practitioner:{title:'General practitioner',steps:[['Listen to the source','source'],['Review facts and SOAP note','note'],['Check verification and approval','note'],['Inspect version and audit history','history']]},
 specialist:{title:'Specialist',steps:[['Review the complete source and speaker turns','source'],['Inspect relevant facts, evidence and uncertainty','note'],['Compare saved note versions','history']]},
 documentation_reviewer:{title:'Documentation reviewer',steps:[['Inspect unreviewed source spans','source'],['Review directional coverage and verification findings','note'],['Compare edits and provenance','history']]},
 read_only_auditor:{title:'Read-only auditor',steps:[['Inspect transcript and source provenance','source'],['Review approved note status and evidence','note'],['Inspect version lineage and content-free audit events','history']]},
} as const;
type Persona=keyof typeof journeys;

export function PersonaJourneys({onSource,onNote,onHistory,disabled}:{onSource:()=>void;onNote:()=>void;onHistory:()=>void;disabled:boolean}){
 const [persona,setPersona]=useState<Persona>('general_practitioner');
 const journey=journeys[persona];
 const open=(destination:string)=>destination==='source'?onSource():destination==='note'?onNote():onHistory();
 return <section className="panel persona-journey" aria-label="Synthetic persona journey">
  <div className="panel-heading"><h2>Local synthetic persona journey</h2><span className="pill">WALKTHROUGH · NOT CLINICAL VALIDATION</span></div>
  <p>Follow the same synthetic encounter from the perspective of a clinical user, documentation reviewer or auditor. Selecting a persona never changes account permissions.</p>
  <label>Review persona<select aria-label="Review persona" value={persona} onChange={event=>setPersona(event.target.value as Persona)}>{Object.entries(journeys).map(([id,item])=><option key={id} value={id}>{item.title}</option>)}</select></label>
  <ol>{journey.steps.map(([label,destination],index)=><li key={`${persona}-${index}`}><span>{index+1}. {label}</span><button type="button" disabled={disabled} onClick={()=>open(destination)}>Open {destination==='source'?'source':destination==='note'?'note':'history'}</button></li>)}</ol>
  <p role="note">Read-only auditor journeys use the current account role; they do not grant or simulate clinician access. No patient data or external service is used by this walkthrough.</p>
 </section>;
}
