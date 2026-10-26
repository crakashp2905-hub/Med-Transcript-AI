import {pcmCapture,type Capture} from './PcmCapture';
import { useEffect, useRef, useState } from 'react';

type Props = {
  disabled:boolean;
  profile:string;
  authorize:()=>Promise<void>;
  submit:(file:File)=>Promise<boolean>;
  onActiveChange:(active:boolean)=>void;
};
const formatTime=(seconds:number)=>`${Math.floor(seconds/60)}:${String(seconds%60).padStart(2,'0')}`;
const MAX_SECONDS=30*60, MAX_BYTES=64*1024*1024;

export function Dictation({disabled,profile,authorize,submit,onActiveChange}:Props){
 const [confirmed,setConfirmed]=useState(false),[phase,setPhase]=useState<'idle'|'starting'|'recording'|'sending'|'saved'|'retry'>('idle');
 const [seconds,setSeconds]=useState(0),[error,setError]=useState(''),[draft,setDraft]=useState<File|null>(null),[url,setUrl]=useState('');
 const [channelCount,setChannelCount]=useState(1),[device,setDevice]=useState(''),[devices,setDevices]=useState<MediaDeviceInfo[]>([]);
 async function findDevices(){try{setDevices((await navigator.mediaDevices.enumerateDevices()).filter(d=>d.kind==='audioinput'));}catch{setError('Could not list audio devices. Check browser permissions.');}}
 const recorder=useRef<Capture|null>(null),stream=useRef<MediaStream|null>(null),chunks=useRef<Blob[]>([]),bytes=useRef(0);
 const mounted=useRef(true),generation=useRef(0),discard=useRef(false),started=useRef(0),timer=useRef<number|undefined>(undefined);
 const interrupted=useRef(false);
 const active=phase==='starting'||phase==='recording';
 const supported=typeof MediaRecorder!=='undefined'&&!!navigator.mediaDevices?.getUserMedia&&window.isSecureContext;
 useEffect(()=>{onActiveChange(active||phase==='retry'||phase==='sending');return()=>onActiveChange(false);},[active,phase,onActiveChange]);

 function release(){if(timer.current!==undefined)window.clearInterval(timer.current);timer.current=undefined;stream.current?.getTracks().forEach(track=>track.stop());stream.current=null;}
 function cancel(){generation.current++;discard.current=true;if(recorder.current?.state==='recording')recorder.current.stop();release();chunks.current=[];setPhase('idle');setSeconds(0);setDraft(null);}
 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;generation.current++;discard.current=true;if(recorder.current?.state==='recording')recorder.current.stop();release();};},[]);
 useEffect(()=>{if(!draft){setUrl('');return;}const next=URL.createObjectURL(draft);setUrl(next);return()=>URL.revokeObjectURL(next);},[draft]);
 useEffect(()=>{if(!active&&phase!=='retry'&&phase!=='sending')return;const leaving=(event:BeforeUnloadEvent)=>{event.preventDefault();event.returnValue='';};window.addEventListener('beforeunload',leaving);return()=>window.removeEventListener('beforeunload',leaving);},[active,phase]);
 async function send(file:File){setPhase('sending');try{const received=await submit(file);if(mounted.current)setPhase(received?'saved':'retry');}catch{if(mounted.current){setError('The recording could not be sent. Your local recording is available to retry.');setPhase('retry');}}}
 async function start(){
  if(disabled||!confirmed||!profile||!supported||active||phase==='retry'||phase==='sending')return;
  const type=channelCount>1?'audio/wav':['audio/webm;codecs=opus','audio/ogg;codecs=opus','audio/mp4'].find(value=>MediaRecorder.isTypeSupported(value));
  if(!type){setError('This browser cannot record a supported audio format. Use Chrome or Edge on localhost, or upload a WAV.');return;}
  const attempt=++generation.current;setPhase('starting');setError('');setDraft(null);setSeconds(0);
  try{
   // Establish server-side authorization before asking for microphone access.
   await authorize();
   if(!mounted.current||attempt!==generation.current)return;
   const input=await navigator.mediaDevices.getUserMedia({audio:{...(device?{deviceId:{exact:device}}:{}),channelCount:channelCount===1?1:{exact:channelCount},echoCancellation:channelCount===1,noiseSuppression:channelCount===1,autoGainControl:channelCount===1},video:false});
   if(!mounted.current||attempt!==generation.current){input.getTracks().forEach(track=>track.stop());return;}
   stream.current=input;
   if(channelCount>1&&input.getAudioTracks()[0]?.getSettings().channelCount!==channelCount)throw new Error('The device did not confirm the requested physical channel count. Use a compatible multichannel interface or upload a multichannel WAV.');
   discard.current=false;interrupted.current=false;chunks.current=[];bytes.current=0;
   const capture:Capture=channelCount>1?await pcmCapture(input,channelCount,(reason)=>{interrupted.current=true;setError(reason||'Multichannel capture stopped at its size limit or was interrupted. Review and save the partial recording.');}):new MediaRecorder(input,{mimeType:type,audioBitsPerSecond:128000});
   if(!mounted.current||attempt!==generation.current){capture.stop();release();return;}
   recorder.current=capture;
   capture.ondataavailable=event=>{if(discard.current||!event.data.size)return;bytes.current+=event.data.size;chunks.current.push(event.data);if(bytes.current>=MAX_BYTES&&capture.state==='recording'){interrupted.current=true;setError('Recording size limit reached. Review and save the partial recording before continuing.');capture.stop();}};
   capture.onerror=()=>{interrupted.current=true;if(mounted.current)setError('Microphone recording was interrupted. Review the partial recording; it may be incomplete or unreadable.');if(capture.state==='recording')capture.stop();};
   capture.onstop=()=>{
    release();if(!mounted.current||discard.current||attempt!==generation.current)return;
    const mime=type.split(';')[0],extension=mime==='audio/wav'?'wav':mime==='audio/mp4'?'m4a':mime==='audio/ogg'?'ogg':'webm';
    const file=new File(chunks.current,`synthetic-dictation-${Date.now()}.${extension}`,{type:mime});chunks.current=[];
    if(!file.size||performance.now()-started.current<1000){if(!interrupted.current)setError('Record at least one second of speech before stopping.');setPhase('idle');return;}
    setDraft(file);if(interrupted.current)setPhase('retry');else void send(file);
   };
   input.getAudioTracks().forEach(track=>{track.onended=()=>{if(capture.state==='recording'&&!discard.current){interrupted.current=true;if(mounted.current)setError('The microphone disconnected. Review and save the partial recording before continuing.');capture.stop();}};});
   started.current=performance.now();capture.start(500);setPhase('recording');
   timer.current=window.setInterval(()=>{const elapsed=Math.floor((performance.now()-started.current)/1000);if(mounted.current)setSeconds(elapsed);if(elapsed>=MAX_SECONDS&&capture.state==='recording')capture.stop();},250);
  }catch(cause){release();if(!mounted.current||attempt!==generation.current)return;setPhase('idle');const name=cause instanceof DOMException?cause.name:'';setError(name==='NotAllowedError'?'Microphone permission was denied. Allow microphone access in the address bar, then try again.':name==='NotFoundError'?'No microphone was found. Connect one, or upload a recording.':name==='NotReadableError'?'The microphone is unavailable or in use by another app.':cause instanceof Error?cause.message:'Could not start the microphone.');}
 }
 return <section className="dictation" aria-labelledby="dictation-heading"><div className="dictation-heading"><div><span className="eyebrow">RECORD HERE</span><h3 id="dictation-heading">Microphone dictation</h3></div><span className={`dictation-timer ${phase==='recording'?'is-recording':''}`} role="timer" aria-label="Recording duration">{phase==='recording'&&<span className="recording-dot"/>}{formatTime(seconds)}</span></div>
 <p>Speak in English, then stop to get a local transcript. Text appears after processing. Maximum 30 minutes or 64 MiB. Keep this tab open; live recording is held in browser memory until saved.</p>
 <button disabled={active||phase==='sending'||phase==='retry'} onClick={()=>void findDevices()}>Refresh input devices</button><label>Input device <select aria-label="Input device" value={device} disabled={active||phase==='sending'||phase==='retry'} onChange={e=>setDevice(e.target.value)}><option value="">System default</option>{devices.filter(d=>d.deviceId&&d.deviceId!=='default').map((d,i)=><option value={d.deviceId} key={d.deviceId}>{d.label||`Audio input ${i+1}`}</option>)}</select></label>
 <label>Physical input channels <select aria-label="Physical input channels" value={channelCount} disabled={active||phase==='retry'||phase==='sending'} onChange={e=>setChannelCount(Number(e.target.value))}>{Array.from({length:8},(_,i)=><option key={i+1} value={i+1}>{i+1}</option>)}</select></label><p>Multiple channels require one synchronized multichannel input device. Channels retain separate timelines and need speaker review. PCM multichannel recordings can reach the 64 MiB limit before 30 minutes.</p>
 <label className="check"><input type="checkbox" checked={confirmed} disabled={active||phase==='sending'} onChange={event=>setConfirmed(event.target.checked)}/>I am dictating synthetic test speech, and recording and local-processing authorization is documented.</label>
 <p className="dictation-model">Local ASR: <strong>{profile||'No model configured'}</strong> · Development model; 5% WER requirement not met.</p>
 {!supported&&<p role="alert">Microphone capture requires a supported browser on localhost or HTTPS. You can still upload audio.</p>}
 {error&&<p role="alert" className="dictation-error">{error}</p>}
 <div className="dictation-controls">{active?<><button className="primary" disabled={phase==='starting'} onClick={()=>{if(recorder.current?.state==='recording')recorder.current.stop();}}>Stop & transcribe</button><button onClick={cancel}>Discard recording</button></>:<button className="primary" disabled={disabled||!confirmed||!supported||!profile||phase==='sending'||phase==='retry'} onClick={()=>void start()}>Start dictation</button>}
 {phase==='retry'&&draft&&<><button disabled={disabled} onClick={()=>void send(draft)}>Retry recording upload</button><button disabled={disabled} onClick={cancel}>Discard partial recording</button></>}</div>
 <p className="dictation-status" role="status" aria-live="polite">{phase==='starting'?'Authorizing and requesting microphone permission…':phase==='recording'?'Recording · microphone is on':phase==='sending'?'Processing your recording locally…':phase==='saved'?'Recording saved. Check the transcription result or job status below.':'The microphone is off.'}</p>
 {draft&&url&&<div className="dictation-preview"><audio controls src={url} aria-label="Dictation recording preview"/><a href={url} download={draft.name}>Save this recording locally</a></div>}
 </section>;
}
