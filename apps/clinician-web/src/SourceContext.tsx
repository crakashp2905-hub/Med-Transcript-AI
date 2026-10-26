type Segment={segment_id:string;start_ms:number;end_ms:number;text:string;role:string;channel_index?:number};
const clock=(ms:number)=>`${Math.floor(ms/60000)}:${String(Math.floor(ms/1000)%60).padStart(2,'0')}`;
export function SourceContext({segments,playback,channel,play,selected,version,historical}:{segments:Segment[];playback:number;channel?:number;play:(ms:number,channel?:number)=>void;selected:string;version:number;historical:boolean}){
 return <section className="panel source-context" aria-label="Source alongside note"><div className="panel-heading"><h2>Source alongside note</h2><span className="muted">Original recording timeline</span></div>
 <p className="muted">Citations play the containing transcript interval. Highlighting is not word alignment.</p>
 <p role="note">Transcript version {version}{historical?' · Historical source bound to this saved note. The current encounter source has changed.':''}</p>
 <div className="context-turns">{segments.map(segment=><article id={`source-${segment.segment_id}`} key={segment.segment_id} className={selected===segment.segment_id?'citation-selected':playback>=segment.start_ms&&playback<segment.end_ms&&(channel===undefined||segment.channel_index===channel)?'playing':''}>
 <button className="timestamp" onClick={()=>play(segment.start_ms,segment.channel_index)} aria-label={`Play source ${clock(segment.start_ms)}`}>{clock(segment.start_ms)}–{clock(segment.end_ms)} ▷</button><strong>{segment.role}{segment.channel_index!==undefined?` · Channel ${segment.channel_index+1}`:''}</strong><p>{segment.text}</p></article>)}</div></section>;
}
