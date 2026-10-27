import {draftMeta,draftSlice,setServer} from './RecordingVault';
type Request=(path:string,options?:RequestInit)=>Promise<any>;
const pending=new Map<string,Promise<number>>();
// Each call drains the committed snapshot. Capture continues independently.
export function syncCapture(id:string,scope:string,eid:string,request:Request):Promise<number>{
 const current=pending.get(id);if(current)return current;
 const task=(async()=>{
  let record=await draftMeta(id,scope),server=record.server;
  if(!server){server=await request(`/v1/encounters/${eid}/stream-uploads`,{method:'POST',headers:{'Idempotency-Key':`capture-${id}`},body:JSON.stringify({format:record.format,channels:record.channels,media_type:record.type})});await setServer(id,scope,server);}
  if(!server)throw new Error('Server backup unavailable');
  const state=await request(`/v1/encounters/${eid}/audio-uploads/${server.id}`),header=record.format==='pcm'?44:0;
  if(state.expired&&state.status!=='complete')throw new Error('Server backup expired. Download the local draft and upload it as a new recording.');
  if(state.stream_sealed)return record.bytes;
  let offset=state.received_bytes;
  if(!Number.isSafeInteger(offset)||offset<header||offset>record.bytes+header)throw new Error('Invalid server backup offset');
  while(offset<record.bytes+header){
   const chunk=await draftSlice(id,scope,offset-header,Math.min(1024*1024,record.bytes+header-offset)),bytes=await chunk.arrayBuffer();
   if(!bytes.byteLength)throw new Error('Missing local recording prefix');
   const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))).map(x=>x.toString(16).padStart(2,'0')).join('');
   const progress=await request(server.content_url,{method:'PATCH',body:chunk,headers:{'Content-Type':record.type,'Upload-Offset':String(offset),'Upload-Chunk-SHA256':hash}});
   if(progress.received_bytes<=offset||progress.received_bytes>record.bytes+header)throw new Error('Invalid server backup progress');offset=progress.received_bytes;
  }
  return offset-header;
 })();pending.set(id,task);void task.finally(()=>{if(pending.get(id)===task)pending.delete(id);}).catch(()=>{});return task;
}
export async function sealCapture(file:File,scope:string,eid:string,sha:string,request:Request){
 const id=(file as File&{captureDraftId?:string}).captureDraftId;if(!id)return null;
 const active=pending.get(id);if(active)await active;
 const record=await draftMeta(id,scope);if(!record.server)return null;
 // An earlier pump may have captured a shorter snapshot. Drain again after it.
 await syncCapture(id,scope,eid,request);await syncCapture(id,scope,eid,request);
 await request(`/v1/encounters/${eid}/stream-uploads/${record.server.id}/seal`,{method:'POST',body:JSON.stringify({bytes:file.size,sha256:sha})});return record.server;
}
