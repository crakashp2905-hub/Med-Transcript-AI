import type {Fact} from './facts';
import type {Finding} from './workspaceTypes';

export function ClinicianCorrection({fact,finding,disabled,record}:{fact:Fact;finding?:Finding;disabled:boolean;record:(findingId:string,fact:Fact)=>void}){
 if(fact.origin!=='source_linked'||fact.excluded||!finding)return null;
 return <div className="callout"><p>Independent confirmation must be a separate clinician addition. The original source remains recorded as excluded evidence.</p>
 <button disabled={disabled||fact.text===fact.evidence?.quote||fact.clarification.trim().length<20} onClick={()=>record(finding.finding_id,fact)}>Record as clinician addition</button>
 <small>Save the corrected wording and a clinical basis of at least 20 characters before recording this explicit clinician action.</small></div>;
}
