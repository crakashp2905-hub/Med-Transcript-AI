import React from 'react';
import type {Segment} from './workspaceTypes';
import {clock} from './format';

const REASONS:Record<string,string>={
 unreviewed_asr:'ASR text has not been checked against the recording.',
 language_support_unverified:'Language support has not been confirmed.',
 speaker_unassigned:'Speaker has not been assigned.',
 channel_is_not_verified_speaker:'Audio channel is not a verified speaker identity.',
 overlapping_model_timestamps:'ASR timestamps overlap another segment.',
 not_transcribed_unknown_cause:'This source interval has no recognized text; the cause is unknown.',
};

type Gap={start_ms:number;end_ms:number;reason:string};
export function UncertainSpanQueue({segments,originalSegments,gaps,onReview}:{segments:Segment[];originalSegments:Segment[];gaps:Gap[];onReview:(segment:Segment)=>void}){
 const originalById=new Map(originalSegments.map(segment=>[segment.segment_id,segment.text]));
 const rows=segments.filter(segment=>(segment.uncertainties?.length||0)>0||segment.role_status==='unconfirmed'||segment.role==='unknown');
 if(!rows.length&&!gaps.length)return null;
 return <section className="uncertain-queue" aria-labelledby="uncertain-queue-title">
  <div className="panel-heading"><h3 id="uncertain-queue-title">Uncertain source spans</h3><span className="pill">{rows.length+gaps.length} to review</span></div>
  <p className="muted">Play each source interval and compare it with the preserved transcript. ASR alternatives are shown only when the recognizer supplied them.</p>
  <ol>{rows.map(segment=>{
   const reasons=[...(segment.uncertainties||[]),...(segment.role_status==='unconfirmed'||segment.role==='unknown'?['speaker_unassigned']:[])];
   return <li key={segment.segment_id}>
    <button type="button" className="timestamp" onClick={()=>onReview(segment)} aria-label={`Play and review source interval starting ${clock(segment.start_ms)}`}>{clock(segment.start_ms)} <span aria-hidden="true">▶</span></button>
    <div><strong>Original ASR text</strong><p className="queue-original">{originalById.get(segment.segment_id)??segment.text}</p>
     <ul className="queue-reasons">{[...new Set(reasons)].map(reason=><li key={reason}>{REASONS[reason]||'This segment requires source review.'}</li>)}</ul>
     {segment.alternatives?.length?<div><strong>Candidate alternatives</strong><ul>{segment.alternatives.map((alternative,index)=><li key={`${index}-${alternative.text}`}>{alternative.text}{alternative.source?` (${alternative.source})`:''}</li>)}</ul></div>:<p className="muted">No alternate hypotheses were supplied for this span.</p>}
    </div>
   </li>;
  })}{gaps.map((gap,index)=><li key={`gap-${gap.start_ms}-${index}`}>
   <button type="button" className="timestamp" onClick={()=>onReview({segment_id:'',start_ms:gap.start_ms,end_ms:gap.end_ms,text:'',role:'unknown'})} aria-label={`Play and review untranscribed interval starting ${clock(gap.start_ms)}`}>{clock(gap.start_ms)} <span aria-hidden="true">▶</span></button>
   <div><strong>Untranscribed source interval</strong><p>{clock(gap.start_ms)}–{clock(gap.end_ms)}</p><p className="queue-reasons">{REASONS[gap.reason]||'No text was transcribed for this interval; review the audio.'}</p></div>
  </li>)}</ol>
 </section>;
}
