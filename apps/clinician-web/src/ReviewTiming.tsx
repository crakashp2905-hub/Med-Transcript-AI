import React,{useEffect,useRef,useState} from 'react';

type Metric={review_wall_ms:number;word_edits:number;self_reported_active_ms:number|null;field_edit_counts?:Record<string,number>};
type Review={id:string;started_at:string;note_version_id:string;completion:Metric|null};
type Request=(path:string,options?:RequestInit)=>Promise<any>;

export function ReviewTiming({encounter,note,dirty,disabled,request}:{encounter:string;note:string;dirty:boolean;disabled:boolean;request:Request}){
 const [items,setItems]=useState<Review[]>([]),[busy,setBusy]=useState(false),[error,setError]=useState(''),[now,setNow]=useState(Date.now());
 const requestId=useRef(crypto.randomUUID()),inflight=useRef(false);
 const base=`/v1/encounters/${encounter}/review-sessions`;
 async function refresh(){setItems((await request(base)).items);}
 useEffect(()=>{let live=true;request(base).then(r=>{if(live)setItems(r.items);}).catch(()=>{if(live)setError('Review timing history could not be loaded.');});return()=>{live=false;};},[encounter]);
 const active=items.find(s=>!s.completion);
 useEffect(()=>{if(!active)return;const timer=window.setInterval(()=>setNow(Date.now()),1000);return()=>clearInterval(timer);},[active?.id]);
 async function act(finish:boolean){if(inflight.current)return;inflight.current=true;setBusy(true);setError('');try{
  if(finish&&active){await request(`${base}/${active.id}/complete`,{method:'POST',body:JSON.stringify({note_version_id:note})});requestId.current=crypto.randomUUID();}
  else await request(base,{method:'POST',body:JSON.stringify({note_version_id:note,client_request_id:requestId.current})});
  await refresh();
 }catch(e){setError(e instanceof Error?e.message:'Review timing request failed.');}finally{setBusy(false);inflight.current=false;}}
 return <section className="panel"><div className="panel-heading"><h2>Review timing</h2></div>
 <p>Measure a review against saved note versions. Wall time includes pauses and inactive tabs; it is not verified active clinician time.</p>
 {active?<><p role="status">Session elapsed: {Math.max(0,Math.floor((now-Date.parse(active.started_at))/1000))} seconds</p><button disabled={disabled||busy||dirty} onClick={()=>void act(true)}>Finish review of saved version</button></>:
 <button disabled={disabled||busy||dirty} onClick={()=>void act(false)}>Start timed review</button>}
 {dirty&&<p>Save your note changes before starting or finishing a review.</p>}
 {error&&<p className="error" role="alert">{error}</p>}
 {items.filter(i=>i.completion).slice(0,5).map(i=><p key={i.id}>Completed: {(i.completion!.review_wall_ms/1000).toFixed(1)} seconds wall time · {i.completion!.word_edits} word edits · {Object.values(i.completion!.field_edit_counts||{}).reduce((a,b)=>a+b,0)} fact-field changes</p>)}
 </section>;
}
