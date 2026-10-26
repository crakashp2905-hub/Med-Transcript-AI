import React, {useState} from 'react';

export type Diarization = {segments:{speaker_id:string|null;role:string;start_ms:number;end_ms:number;channel_index?:number}[];role_assignment:string;overlap_detection?:string};

export function SpeakerRoles({report,disabled,play,save}:{report:Diarization;disabled:boolean;play:(ms:number,channel?:number)=>void;save:(roles:Record<string,string>)=>Promise<void>}) {
 const speakers=[...new Set(report.segments.map(s=>s.speaker_id).filter((s):s is string=>s!==null))];
 const [roles,setRoles]=useState<Record<string,string>>(()=>Object.fromEntries(speakers.map(s=>[s,report.segments.find(t=>t.speaker_id===s)?.role||'unknown'])));
 const [confirmed,setConfirmed]=useState(false);
 return <section className="panel"><div className="panel-heading"><h2>Confirm speaker roles</h2></div>
 <p>Listen to each anonymous speaker before confirming their role. Leave uncertain roles unknown. Channels and speaker clusters are development features; a channel may contain cross-talk or multiple people.</p>
 {report.overlap_detection==='unsupported'&&<p className="callout">This model does not separate overlapping voices. Review overlapping speech and speaker changes in the recording.</p>}
 {speakers.map(s=><label key={s}>{s.replace('_',' ')} <button type="button" disabled={disabled} onClick={()=>play(report.segments.find(t=>t.speaker_id===s)!.start_ms,report.segments.find(t=>t.speaker_id===s)!.channel_index)}>Play example</button>
 <select aria-label={`Role for ${s}`} disabled={disabled} value={roles[s]} onChange={e=>{setRoles({...roles,[s]:e.target.value});setConfirmed(false);}}>{['unknown','patient','clinician','caregiver','interpreter','other'].map(role=><option key={role}>{role}</option>)}</select></label>)}
 <label className="check"><input type="checkbox" disabled={disabled} checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>I listened to the speakers and reviewed these role assignments.</label>
 <button disabled={disabled||!confirmed||!speakers.length} onClick={()=>void save(roles)}>Save speaker confirmation</button>
 <p className="muted">Confirmation creates a new source version. Segments crossing speaker boundaries remain unknown.</p>
 </section>;
}
