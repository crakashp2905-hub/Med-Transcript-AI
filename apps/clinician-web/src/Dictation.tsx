import {pcmFile,createDraft,appendDraft,readDraft,listDrafts,deleteDraft,type DraftRecord} from './RecordingVault';
import {pcmCapture,type Capture} from './PcmCapture';
import {DeviceCheck} from './DeviceCheck';
import { useEffect, useRef, useState } from 'react';

type Props = {
  storageScope:string;
  backup:(id:string)=>Promise<number>;
  permission:()=>Promise<boolean>;
  preview:(file:File,startMs:number)=>Promise<{start_ms:number;end_ms:number;text:string;channel_index?:number}[]>;
  disabled:boolean;
  profile:string;
  authorize:()=>Promise<void>;
  submit:(file:File)=>Promise<boolean>;
  onActiveChange:(active:boolean)=>void;
};
const formatTime=(seconds:number)=>`${Math.floor(seconds/60)}:${String(seconds%60).padStart(2,'0')}`;
const MAX_SECONDS=30*60, MAX_BYTES=511999956;

export function Dictation({backup,permission,preview,storageScope,disabled,profile,authorize,submit,onActiveChange}:Props){
 const [deviceChecking,setDeviceChecking]=useState(false);
 const [confirmed,setConfirmed]=useState(false),[phase,setPhase]=useState<'idle'|'starting'|'recording'|'sending'|'saved'|'retry'>('idle');
 const [seconds,setSeconds]=useState(0),[error,setError]=useState(''),[draft,setDraft]=useState<File|null>(null),[url,setUrl]=useState('');
 const [channelCount,setChannelCount]=useState(1),[device,setDevice]=useState(''),[devices,setDevices]=useState<MediaDeviceInfo[]>([]);
 async function findDevices(){try{setDevices((await navigator.mediaDevices.enumerateDevices()).filter(d=>d.kind==='audioinput'));}catch{setError('Could not list audio devices. Check browser permissions.');}}
 const recorder=useRef<Capture|null>(null),stream=useRef<MediaStream|null>(null),bytes=useRef(0);
 const recordingId=useRef(''),writes=useRef<Promise<void>>(Promise.resolve()),queuedBytes=useRef(0),persistenceFailed=useRef(false);
 const [livePreview,setLivePreview]=useState(false),[previewRows,setPreviewRows]=useState<{start_ms:number;end_ms:number;text:string;channel_index?:number}[]>([]),[previewNotice,setPreviewNotice]=useState('');
 const previewBusy=useRef(false),previewParts=useRef<Blob[]>([]),previewBytes=useRef(0),previewStart=useRef(0);
 const [serverBackup,setServerBackup]=useState(false),[serverNotice,setServerNotice]=useState('');
 const backupAt=useRef(0),backupBusy=useRef(false);
 const [recoveries,setRecoveries]=useState<DraftRecord[]>([]),[savedBytes,setSavedBytes]=useState(0);
 useEffect(()=>{let active=true;listDrafts(storageScope).then(rows=>{if(active)setRecoveries(rows);}).catch(()=>setError('Local recovery storage is unavailable. Recording will not start until browser storage is available.'));return()=>{active=false;};},[storageScope]);
 async function recover(id:string){const attempt=++generation.current;setPhase('sending');try{const file=await readDraft(id,storageScope);if(!mounted.current||attempt!==generation.current)return;recordingId.current=id;setDraft(file);setPhase('retry');setError('Recovered committed audio after an interruption. Review the partial recording before uploading; its ending may be missing.');}catch{if(mounted.current&&attempt===generation.current){setPhase('idle');setError('The local draft could not be read. Keep it for recovery or explicitly delete it.');}}}
 async function removeRecovery(id:string){try{await deleteDraft(id);setRecoveries(rows=>rows.filter(r=>r.id!==id));}catch{setError('The local draft could not be deleted. It remains in browser recovery storage; retry deletion before clearing this browser.');}}
 const mounted=useRef(true),generation=useRef(0),discard=useRef(false),started=useRef(0),timer=useRef<number|undefined>(undefined);
 const interrupted=useRef(false),permissionTimer=useRef<number|undefined>(undefined),permissionPending=useRef(false);
 const active=phase==='starting'||phase==='recording';
 const supported=typeof MediaRecorder!=='undefined'&&!!navigator.mediaDevices?.getUserMedia&&window.isSecureContext;
 useEffect(()=>{onActiveChange(deviceChecking||active||phase==='retry'||phase==='sending');return()=>onActiveChange(false);},[deviceChecking,active,phase,onActiveChange]);

 function release(){if(permissionTimer.current!==undefined)window.clearInterval(permissionTimer.current);permissionTimer.current=undefined;if(timer.current!==undefined)window.clearInterval(timer.current);timer.current=undefined;stream.current?.getTracks().forEach(track=>track.stop());stream.current=null;}
 function cancel(){generation.current++;discard.current=true;if(recorder.current?.state==='recording')recorder.current.stop();release();const id=recordingId.current;recordingId.current='';if(id)void writes.current.then(()=>removeRecovery(id));setPhase('idle');setSeconds(0);setDraft(null);}
 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;generation.current++;discard.current=true;if(recorder.current?.state==='recording')recorder.current.stop();release();};},[]);
 useEffect(()=>{if(!draft){setUrl('');return;}const next=URL.createObjectURL(draft);setUrl(next);return()=>URL.revokeObjectURL(next);},[draft]);
 useEffect(()=>{if(!active&&phase!=='retry'&&phase!=='sending')return;const leaving=(event:BeforeUnloadEvent)=>{event.preventDefault();event.returnValue='';};window.addEventListener('beforeunload',leaving);return()=>window.removeEventListener('beforeunload',leaving);},[active,phase]);
 async function send(file:File,renewAuthorization=false){setPhase('sending');try{if(renewAuthorization)await authorize();const received=await submit(file);if(received&&recordingId.current){await removeRecovery(recordingId.current);recordingId.current='';}if(mounted.current){if(!received)setConfirmed(false);setPhase(received?'saved':'retry');}}catch{if(mounted.current){setError('The recording could not be sent. Your local recording is available to retry.');setPhase('retry');}}}
 async function start(){
  if(deviceChecking||disabled||!confirmed||!profile||!supported||active||phase==='retry'||phase==='sending')return;
  const usePcm=channelCount>1||livePreview;
  const type=usePcm?'audio/wav':['audio/webm;codecs=opus','audio/ogg;codecs=opus','audio/mp4'].find(value=>MediaRecorder.isTypeSupported(value));
  if(!type){setError('This browser cannot record a supported audio format. Use Chrome or Edge on localhost, or upload a WAV.');return;}
  const attempt=++generation.current;setPhase('starting');setError('');setDraft(null);setSeconds(0);setServerNotice('');backupAt.current=0;
  try{
   // Establish server-side authorization before asking for microphone access.
   await authorize();
   if(!mounted.current||attempt!==generation.current)return;
   const input=await navigator.mediaDevices.getUserMedia({audio:{...(device?{deviceId:{exact:device}}:{}),channelCount:usePcm?{exact:channelCount}:1,echoCancellation:channelCount===1,noiseSuppression:channelCount===1,autoGainControl:channelCount===1},video:false});
   if(!mounted.current||attempt!==generation.current){input.getTracks().forEach(track=>track.stop());return;}
   stream.current=input;
   if(channelCount>1&&input.getAudioTracks()[0]?.getSettings().channelCount!==channelCount)throw new Error('The device did not confirm the requested physical channel count. Use a compatible multichannel interface or upload a multichannel WAV.');
   discard.current=false;interrupted.current=false;bytes.current=0;savedBytes&&setSavedBytes(0);persistenceFailed.current=false;queuedBytes.current=0;writes.current=Promise.resolve();
   const mime=type.split(';')[0],extension=mime==='audio/wav'?'wav':mime==='audio/mp4'?'m4a':mime==='audio/ogg'?'ogg':'webm';
   const id=await createDraft(storageScope,`synthetic-dictation-${Date.now()}.${extension}`,mime,usePcm?'pcm':'media',channelCount);if(!mounted.current||attempt!==generation.current){await deleteDraft(id);input.getTracks().forEach(track=>track.stop());return;}recordingId.current=id;
   const capture:Capture=usePcm?await pcmCapture(input,channelCount,(reason)=>{interrupted.current=true;setError(reason||'Multichannel capture stopped at its size limit or was interrupted. Review and save the partial recording.');}):new MediaRecorder(input,{mimeType:type,audioBitsPerSecond:128000});
   if(!mounted.current||attempt!==generation.current){capture.stop();input.getTracks().forEach(track=>track.stop());await deleteDraft(id);if(recordingId.current===id)recordingId.current='';return;}
   recorder.current=capture;previewParts.current=[];previewBytes.current=0;previewStart.current=0;previewBusy.current=false;setPreviewRows([]);setPreviewNotice('');
   function offerPreview(data:Blob){
    if(!livePreview)return;previewParts.current.push(data);previewBytes.current+=data.size;
    if(previewBytes.current<16000*channelCount*2*10)return;
    const start=previewStart.current;previewStart.current+=previewBytes.current/(channelCount*32);
    const file=pcmFile(previewParts.current,channelCount);previewParts.current=[];previewBytes.current=0;
    if(previewBusy.current){setPreviewNotice('Some intervals were not previewed because local ASR was busy. The complete saved recording will be transcribed after stopping.');return;}
    previewBusy.current=true;setPreviewNotice('Processing a provisional local preview…');
    void preview(file,Math.round(start)).then(rows=>{if(mounted.current&&attempt===generation.current){setPreviewRows(old=>[...old,...rows].slice(-200));setPreviewNotice('Provisional preview only. Review the full transcript after stopping.');}}).catch(()=>{if(mounted.current&&attempt===generation.current)setPreviewNotice('Local preview did not complete. Recording and recovery continue; the complete recording will be processed after stopping.');}).finally(()=>{if(attempt===generation.current)previewBusy.current=false;});
   }
   capture.ondataavailable=event=>{
    if(attempt!==generation.current||discard.current||!event.data.size||persistenceFailed.current)return;
    const data=event.data;offerPreview(data);bytes.current+=data.size;queuedBytes.current+=data.size;
    writes.current=writes.current.then(async()=>{if(attempt!==generation.current||persistenceFailed.current)return;await appendDraft(id,data);if(attempt===generation.current)queuedBytes.current-=data.size;if(mounted.current&&attempt===generation.current){setSavedBytes(value=>value+data.size);if(serverBackup&&!backupBusy.current&&Date.now()-backupAt.current>=2000){backupAt.current=Date.now();backupBusy.current=true;void backup(id).then(count=>{if(mounted.current&&attempt===generation.current)setServerNotice(`Server acknowledged ${(count/1024/1024).toFixed(1)} MiB. Only this prefix is recoverable if browser storage is lost.`);}).catch(()=>{if(mounted.current&&attempt===generation.current)setServerNotice('Server backup is interrupted. Local browser recovery continues; keep this browser storage.');}).finally(()=>{backupBusy.current=false;});}}}).catch(()=>{if(attempt!==generation.current)return;persistenceFailed.current=true;interrupted.current=true;if(mounted.current)setError('Browser storage failed or is full. Capture stopped. Only previously saved chunks can be recovered.');if(capture.state==='recording')capture.stop();});
    if(queuedBytes.current>8*1024*1024&&capture.state==='recording'){interrupted.current=true;setError('Browser storage is too slow. Capture stopped to keep recovery memory bounded; review the saved partial recording.');capture.stop();}
    if(bytes.current>=MAX_BYTES&&capture.state==='recording'){interrupted.current=true;setError('Recording size limit reached. Review and save the partial recording before continuing.');capture.stop();}
   };
   capture.onerror=()=>{if(attempt!==generation.current)return;interrupted.current=true;if(mounted.current)setError('Microphone recording was interrupted. Review the partial recording; it may be incomplete or unreadable.');if(capture.state==='recording')capture.stop();};
   capture.onstop=async()=>{
    release();previewParts.current=[];previewBytes.current=0;await writes.current;if(!mounted.current||discard.current||attempt!==generation.current)return;
    if(!bytes.current||performance.now()-started.current<1000){if(!interrupted.current)setError('Record at least one second of speech before stopping.');await removeRecovery(id);recordingId.current='';setPhase('idle');return;}
    try{const file=await readDraft(id,storageScope);if(!mounted.current||discard.current||attempt!==generation.current)return;setDraft(file);if(interrupted.current)setPhase('retry');else void send(file);}
    catch{setError('Saved chunks remain in local recovery storage, but the recording could not be assembled. Reload to recover it.');setPhase('idle');}
   };
   input.getAudioTracks().forEach(track=>{track.onended=()=>{if(capture.state==='recording'&&!discard.current){interrupted.current=true;if(mounted.current)setError('The microphone disconnected. Review and save the partial recording before continuing.');capture.stop();}};});
   started.current=performance.now();capture.start(500);setPhase('recording');
   permissionTimer.current=window.setInterval(()=>{if(permissionPending.current||capture.state!=='recording')return;permissionPending.current=true;void permission().then(ok=>{if(!ok)throw new Error('authorization_inactive');}).catch(()=>{if(capture.state==='recording'){interrupted.current=true;setConfirmed(false);setError('Recording authorization is inactive or could not be checked. Capture stopped; review the saved partial recording before any upload.');capture.stop();}}).finally(()=>{permissionPending.current=false;});},5000);
   timer.current=window.setInterval(()=>{const elapsed=Math.floor((performance.now()-started.current)/1000);if(mounted.current)setSeconds(elapsed);if(elapsed>=MAX_SECONDS&&capture.state==='recording')capture.stop();},250);
  }catch(cause){if(!mounted.current||attempt!==generation.current)return;release();if(recordingId.current&&!bytes.current){await deleteDraft(recordingId.current).catch(()=>{});recordingId.current='';}if(!mounted.current||attempt!==generation.current)return;setPhase('idle');const name=cause instanceof DOMException?cause.name:'';setError(name==='NotAllowedError'?'Microphone permission was denied. Allow microphone access in the address bar, then try again.':name==='NotFoundError'?'No microphone was found. Connect one, or upload a recording.':name==='NotReadableError'?'The microphone is unavailable or in use by another app.':cause instanceof Error?cause.message:'Could not start the microphone.');}
 }
 return <section className="dictation" aria-labelledby="dictation-heading"><div className="dictation-heading"><div><span className="eyebrow">RECORD HERE</span><h3 id="dictation-heading">Microphone dictation</h3></div><span className={`dictation-timer ${phase==='recording'?'is-recording':''}`} role="timer" aria-label="Recording duration">{phase==='recording'&&<span className="recording-dot"/>}{formatTime(seconds)}</span></div>
 <p>Speak in English, then stop to get a local transcript. Text appears after processing. Maximum 30 minutes or 512 MB. Audio chunks are saved in this browser for interruption recovery. Do not clear browser storage before saving or deleting your drafts.</p>
 <button disabled={deviceChecking||active||phase==='sending'||phase==='retry'} onClick={()=>void findDevices()}>Refresh input devices</button><label>Input device <select aria-label="Input device" value={device} disabled={deviceChecking||active||phase==='sending'||phase==='retry'} onChange={e=>setDevice(e.target.value)}><option value="">System default</option>{devices.filter(d=>d.deviceId&&d.deviceId!=='default').map((d,i)=><option value={d.deviceId} key={d.deviceId}>{d.label||`Audio input ${i+1}`}</option>)}</select></label>
 <label className="check"><input type="checkbox" checked={serverBackup} disabled={deviceChecking||active||phase==='sending'||phase==='retry'} onChange={event=>setServerBackup(event.target.checked)}/>Back up recording chunks to the local server while recording</label><p>Optional server backup stores acknowledged prefixes before stopping. Discarding a local draft does not delete server backups; encounter retention controls apply.</p><p role="status">{serverNotice}</p>
 <label className="check"><input type="checkbox" checked={livePreview} disabled={deviceChecking||active||phase==='sending'||phase==='retry'} onChange={event=>setLivePreview(event.target.checked)}/>Show provisional local previews while recording</label><p>Previews process approximately ten-second windows, may lag or skip intervals when busy, and cannot be approved. The complete recording is transcribed separately after stopping.</p>
 <label>Physical input channels <select aria-label="Physical input channels" value={channelCount} disabled={deviceChecking||active||phase==='retry'||phase==='sending'} onChange={e=>setChannelCount(Number(e.target.value))}>{Array.from({length:8},(_,i)=><option key={i+1} value={i+1}>{i+1}</option>)}</select></label><p>Multiple channels require one synchronized multichannel input device. Channels retain separate timelines and need speaker review. PCM multichannel recordings can require sufficient browser disk quota; 30 minutes at eight channels uses about 461 MB.</p>
 <label className="check"><input type="checkbox" checked={confirmed} disabled={deviceChecking||active||phase==='sending'} onChange={event=>setConfirmed(event.target.checked)}/>I am dictating synthetic test speech, and recording and local-processing authorization is documented.</label>
 <DeviceCheck device={device} channels={channelCount} disabled={disabled||!confirmed||active||phase==='sending'||phase==='retry'} authorize={authorize} onChecking={setDeviceChecking}/>
 <p className="dictation-model">Local ASR: <strong>{profile||'No model configured'}</strong> · Development model; 5% WER requirement not met.</p>
 {!supported&&<p role="alert">Microphone capture requires a supported browser on localhost or HTTPS. You can still upload audio.</p>}
 {error&&<p role="alert" className="dictation-error">{error}</p>}
 <div className="dictation-controls">{active?<><button className="primary" disabled={phase==='starting'} onClick={()=>{if(recorder.current?.state==='recording')recorder.current.stop();}}>Stop & transcribe</button><button onClick={cancel}>Discard recording</button></>:<button className="primary" disabled={deviceChecking||disabled||!confirmed||!supported||!profile||phase==='sending'||phase==='retry'} onClick={()=>void start()}>Start dictation</button>}
 {phase==='retry'&&draft&&<><button disabled={disabled||!confirmed} onClick={()=>void send(draft,true)}>Retry recording upload</button><button disabled={disabled} onClick={cancel}>Discard partial recording</button></>}</div>
 <p className="dictation-status" role="status" aria-live="polite">{phase==='starting'?'Authorizing and requesting microphone permission…':phase==='recording'?'Recording · microphone is on':phase==='sending'?'Processing your recording locally…':phase==='saved'?'Recording saved. Check the transcription result or job status below.':'The microphone is off.'}</p>
 <p className="muted">Committed recovery audio: {(savedBytes/1024/1024).toFixed(1)} MiB. Recovery is local to this browser and encounter; it may omit the last uncommitted chunk. Local drafts are unencrypted synthetic audio and remain until uploaded or explicitly deleted.</p>
 {livePreview&&<section aria-label="Provisional dictation preview"><h4>Live encounter timeline · PROVISIONAL · NOT A SAVED TRANSCRIPT</h4><p role="note">{previewNotice||'Waiting for enough audio for a local preview.'}</p>{previewRows.map((row,i)=><p className="timeline-event" key={i}>{formatTime(Math.floor(row.start_ms/1000))}{row.channel_index!==undefined?` · Channel ${row.channel_index+1}`:''}: {row.text}</p>)}</section>}
 {recoveries.length>0&&<section aria-label="Unfinished recordings"><h4>Unfinished recordings</h4>{recoveries.map(row=><div key={row.id}><span>{row.name} · {(row.bytes/1024/1024).toFixed(1)} MiB</span><button disabled={deviceChecking||active||phase==='sending'||phase==='retry'} onClick={()=>void recover(row.id)}>Recover unfinished recording</button><button disabled={deviceChecking||active||phase==='sending'||phase==='retry'} onClick={()=>void removeRecovery(row.id)}>Delete local draft</button></div>)}</section>}
 {draft&&url&&<div className="dictation-preview"><audio controls src={url} aria-label="Dictation recording preview"/><a href={url} download={draft.name}>Save this recording locally</a></div>}
 </section>;
}
