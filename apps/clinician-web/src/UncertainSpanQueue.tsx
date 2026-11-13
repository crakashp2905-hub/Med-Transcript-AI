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
function WaveformInterval({peaks,start,end,duration}:{peaks:number[]|null;start:number;end:number;duration:number}){
 if(peaks===null)return <p className="muted waveform-status">Loading audio waveform…</p>;
 if(!peaks.length||duration<=0)return <p className="muted waveform-status">Waveform unavailable; use source playback.</p>;
 const x0=Math.max(0,Math.min(1000,start/duration*1000)),x1=Math.max(x0+2,Math.min(1000,end/duration*1000));
 return <svg className="uncertain-waveform" viewBox="0 0 1000 64" role="img" aria-label={"Audio waveform with selected interval from "+clock(start)+" to "+clock(end)}>
  <rect x={x0} y="0" width={x1-x0} height="64" className="waveform-selection"/>
  {peaks.map((peak,index)=>{const height=Math.max(2,peak*58);const x=(index+.5)*1000/peaks.length;return <line key={index} x1={x} x2={x} y1={(64-height)/2} y2={(64+height)/2} className="waveform-peak"/>})}
 </svg>;
}
export function UncertainSpanQueue({segments,originalSegments,gaps,onReview,peaks,duration}:{segments:Segment[];originalSegments:Segment[];gaps:Gap[];onReview:(segment:Segment)=>void;peaks:number[]|null;duration:number}){
 const originalById=new Map(originalSegments.map(segment=>[segment.segment_id,segment.text]));
 const rows=segments.filter(segment=>(segment.uncertainties?.length||0)>0||segment.role_status==='unconfirmed'||segment.role==='unknown');
 if(!rows.length&&!gaps.length)return null;
 return <section className="uncertain-queue" aria-labelledby="uncertain-queue-title">
  <div className="panel-heading"><h3 id="uncertain-queue-title">Uncertain source spans</h3><span className="pill">{rows.length+gaps.length} to review</span></div>
  <p className="muted">Play each source interval and compare it with the preserved transcript. Review priority reflects explicit source uncertainty and rule severity; no uncalibrated confidence probability is shown. ASR alternatives are shown only when the recognizer supplied them.</p>
  <ol>{rows.map(segment=>{
   const reasons=[...(segment.uncertainties||[]),...(segment.role_status==='unconfirmed'||segment.role==='unknown'?['speaker_unassigned']:[])];
   return <li key={segment.segment_id}>
    <button type="button" className="timestamp" onClick={()=>onReview(segment)} aria-label={`Play and review source interval starting ${clock(segment.start_ms)}`}>{clock(segment.start_ms)} <span aria-hidden="true">▶</span></button>
    <div><strong>Original ASR text</strong><p className="queue-original">{originalById.get(segment.segment_id)??segment.text}</p>
     <ul className="queue-reasons">{[...new Set(reasons)].map(reason=><li key={reason}>{REASONS[reason]||'This segment requires source review.'}</li>)}</ul>
     {segment.alternatives?.length?<div><strong>Candidate alternatives</strong><ul>{segment.alternatives.map((alternative,index)=><li key={index+'-'+alternative.text}>{alternative.text}{alternative.source?' ('+alternative.source+')':''}</li>)}</ul></div>:<p className="muted">No alternate hypotheses were supplied for this span.</p>}
     <WaveformInterval peaks={peaks} start={segment.start_ms} end={segment.end_ms} duration={duration}/>
    </div>
   </li>;
  })}{gaps.map((gap,index)=><li key={`gap-${gap.start_ms}-${index}`}>
   <button type="button" className="timestamp" onClick={()=>onReview({segment_id:'',start_ms:gap.start_ms,end_ms:gap.end_ms,text:'',role:'unknown'})} aria-label={`Play and review untranscribed interval starting ${clock(gap.start_ms)}`}>{clock(gap.start_ms)} <span aria-hidden="true">▶</span></button>
   <div><strong>Untranscribed source interval</strong><p>{clock(gap.start_ms)}–{clock(gap.end_ms)}</p><p className="queue-reasons">{REASONS[gap.reason]||'No text was transcribed for this interval; review the audio.'}</p><WaveformInterval peaks={peaks} start={gap.start_ms} end={gap.end_ms} duration={duration}/></div>
  </li>)}</ol>
 </section>;
}
