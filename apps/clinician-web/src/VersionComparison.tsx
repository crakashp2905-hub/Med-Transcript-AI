import React,{useEffect,useState} from 'react';

type Version={id:string;version:number};
type Comparison={source_changed:boolean;unchanged_facts:number;changes:{fact_id:string;change:string;changed_fields:string[];before:Record<string,unknown>|null;after:Record<string,unknown>|null}[]};

export function VersionComparison({encounter,request}:{encounter:string;request:(path:string)=>Promise<any>}){
 const [versions,setVersions]=useState<Version[]>([]),[left,setLeft]=useState(''),[right,setRight]=useState('');
 const [result,setResult]=useState<Comparison|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
 useEffect(()=>{let live=true;request(`/v1/encounters/${encounter}/versions`).then(r=>{if(live){setVersions(r.notes);setLeft(r.notes[1]?.id||r.notes[0]?.id||'');setRight(r.notes[0]?.id||'');}}).catch(()=>{if(live)setError('Versions could not be loaded.');});return()=>{live=false;};},[encounter]);
 async function compare(){setBusy(true);setError('');try{setResult(await request(`/v1/encounters/${encounter}/notes/${left}/compare/${right}`));}catch(e){setError(e instanceof Error?e.message:'Comparison failed.');}finally{setBusy(false);}}
 return <section className="panel"><div className="panel-heading"><h2>Compare saved note versions</h2></div>
 <div className="comparison-grid"><label>Before<select value={left} onChange={e=>{setLeft(e.target.value);setResult(null);}}>{versions.map(v=><option value={v.id} key={v.id}>Version {v.version}</option>)}</select></label>
 <label>After<select value={right} onChange={e=>{setRight(e.target.value);setResult(null);}}>{versions.map(v=><option value={v.id} key={v.id}>Version {v.version}</option>)}</select></label></div>
 <button disabled={busy||!left||!right} onClick={()=>void compare()}>Compare versions</button>
 {error&&<p role="alert" className="error">{error}</p>}
 {result&&<><p>{result.unchanged_facts} unchanged facts · {result.changes.length} changed facts{result.source_changed?' · Source transcript changed':''}</p>
 {result.changes.map(row=><article key={row.fact_id}><h3>{row.change} fact</h3><p>{row.changed_fields.join(', ')}</p><div className="comparison-grid">{(['before','after'] as const).map(side=><div key={side}><strong>{side}</strong><pre>{row[side]?JSON.stringify(Object.fromEntries(row.changed_fields.map(k=>[k,row[side]![k]])),null,2):'Not present'}</pre></div>)}</div></article>)}</>}
 </section>;
}
