import type {RetranscriptionComparison,Segment} from './workspaceTypes';

export function RetranscriptionCompare({candidate,currentSegments,clear}:{candidate:RetranscriptionComparison|null;currentSegments:Segment[];clear:()=>void}){
 if(!candidate)return null;
 const current=currentSegments.find(segment=>segment.segment_id===candidate.segment_id);
 const edited=current&&current.text!==candidate.source_text?current.text:null;
 return <section className="panel retranscription-compare" aria-label="Localized retranscription comparison">
  <div className="panel-heading"><h3>Localized retranscription candidate</h3><span className="pill">UNAPPROVED · NOT A SAVED CORRECTION</span></div>
  <p className="muted">Transcript version bound to this candidate: {candidate.transcript_version_id} · {Math.floor(candidate.start_ms/1000)}–{Math.floor(candidate.end_ms/1000)} seconds{candidate.channel_index===undefined?'':` · Channel ${candidate.channel_index+1}`} · Audio SHA-256 {candidate.span_audio_sha256.slice(0,16)}…</p>
  <div className="comparison-grid"><div><strong>Original transcript</strong><p>{candidate.source_text}</p></div><div><strong>Localized ASR candidate</strong><p>{candidate.candidate_text||'No words returned for this span.'}</p></div><div><strong>Clinician correction</strong><p>{edited||'No clinician edit saved in the source editor.'}</p></div></div>
  <p role="note">The candidate has not changed the transcript or note. Review the audio, edit the source transcript, and save a new version to record a correction.</p>
  <button type="button" onClick={clear}>Dismiss candidate</button>
 </section>;
}
