import type {Transcript} from './workspaceTypes';

function measuredSeconds(value:unknown){return typeof value==='number'&&Number.isFinite(value)&&value>=0?`${value.toFixed(2)} s`:'Unavailable';}

export function ExecutionMetrics({transcript}:{transcript:Transcript}){
 const provenance=transcript.provenance;
 const timing=provenance.timing||{};
 const worker=provenance.worker_timing||{};
 const label=provenance.profile_id||provenance.model_id||(provenance.engine&&provenance.engine!=='manual'?provenance.engine:null);
 return <section className="execution-metrics" aria-label="Measured transcription execution">
  <h3>Execution details</h3>
  <dl>
   <div><dt>Model or engine</dt><dd>{label||'Unavailable'}</dd></div>
   <div><dt>Model revision</dt><dd>{provenance.model_revision||'Unavailable'}</dd></div>
   <div><dt>Worker time</dt><dd>{measuredSeconds(worker.wall_seconds)}</dd></div>
   <div><dt>Model load time</dt><dd>{measuredSeconds(timing.model_load_seconds)}</dd></div>
   <div><dt>Inference time</dt><dd>{measuredSeconds(timing.inference_seconds)}</dd></div>
   <div><dt>Cost</dt><dd>Unavailable · no measured cost recorded</dd></div>
  </dl>
  <p>Times are shown only when recorded for this transcript. Worker time is not a controlled latency benchmark.</p>
 </section>;
}
