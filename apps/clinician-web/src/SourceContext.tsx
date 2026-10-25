type Segment={segment_id:string;start_ms:number;end_ms:number;text:string;role:string};
const clock=(ms:number)=>`${Math.floor(ms/60000)}:${String(Math.floor(ms/1000)%60).padStart(2,'0')}`;
export function SourceContext({segments,playback,play,selected}:{segments:Segment[];playback:number;play:(ms:number)=>void;selected:string}){
 return <section className="panel source-context" aria-label="Source alongside note"><div className="panel-heading"><h2>Source alongside note</h2><span className="muted">Original recording timeline</span></div>
 <p className="muted">Citations play the containing transcript interval. Highlighting is not word alignment.</p>
 <div className="context-turns">{segments.map(segment=><article id={`source-${segment.segment_id}`} key={segment.segment_id} className={selected===segment.segment_id?'citation-selected':playback>=segment.start_ms&&playback<segment.end_ms?'playing':''}>
 <button className="timestamp" onClick={()=>play(segment.start_ms)} aria-label={`Play source ${clock(segment.start_ms)}`}>{clock(segment.start_ms)}–{clock(segment.end_ms)} ▷</button><strong>{segment.role}</strong><p>{segment.text}</p></article>)}</div></section>;
}
