import { useEffect, useRef, useState } from 'react';

type Props = {
  disabled:boolean;
  profile:string;
  authorize:()=>Promise<void>;
  submit:(file:File)=>Promise<boolean>;
  onActiveChange:(active:boolean)=>void;
};
const formatTime=(seconds:number)=>`${Math.floor(seconds/60)}:${String(seconds%60).padStart(2,'0')}`;
const MAX_SECONDS=300, MAX_BYTES=25*1024*1024;

export function Dictation({disabled,profile,authorize,submit,onActiveChange}:Props){
 const [confirmed,setConfirmed]=useState(false),[phase,setPhase]=useState<'idle'|'starting'|'recording'|'sending'|'saved'|'retry'>('idle');
 const [seconds,setSeconds]=useState(0),[error,setError]=useState(''),[draft,setDraft]=useState<File|null>(null),[url,setUrl]=useState('');
 const recorder=useRef<MediaRecorder|null>(null),stream=useRef<MediaStream|null>(null),chunks=useRef<Blob[]>([]),bytes=useRef(0);
 const mounted=useRef(true),generation=useRef(0),discard=useRef(false),started=useRef(0),timer=useRef<number|undefined>(undefined);
 const active=phase==='starting'||phase==='recording';
 const supported=typeof MediaRecorder!=='undefined'&&!!navigator.mediaDevices?.getUserMedia&&window.isSecureContext;
 useEffect(()=>{onActiveChange(active);return()=>onActiveChange(false);},[active,onActiveChange]);

 function release(){if(timer.current!==undefined)window.clearInterval(timer.current);timer.current=undefined;stream.current?.getTracks().forEach(track=>track.stop());stream.current=null;}
 function cancel(){generation.current++;discard.current=true;if(recorder.current?.state==='recording')recorder.current.stop();release();chunks.current=[];setPhase('idle');setSeconds(0);setDraft(null);}
 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;generation.current++;discard.current=true;if(recorder.current?.state==='recording')recorder.current.stop();release();};},[]);
 useEffect(()=>{if(!draft){setUrl('');return;}const next=URL.createObjectURL(draft);setUrl(next);return()=>URL.revokeObjectURL(next);},[draft]);
 useEffect(()=>{if(!active)return;const leaving=(event:BeforeUnloadEvent)=>{event.preventDefault();event.returnValue='';};window.addEventListener('beforeunload',leaving);return()=>window.removeEventListener('beforeunload',leaving);},[active]);
 async function send(file:File){setPhase('sending');try{const received=await submit(file);if(mounted.current)setPhase(received?'saved':'retry');}catch{if(mounted.current){setError('The recording could not be sent. Your local recording is available to retry.');setPhase('retry');}}}
 async function start(){
  if(disabled||!confirmed||!profile||!supported||active)return;
  const type=['audio/webm;codecs=opus','audio/ogg;codecs=opus','audio/mp4'].find(value=>MediaRecorder.isTypeSupported(value));
  if(!type){setError('This browser cannot record a supported audio format. Use Chrome or Edge on localhost, or upload a WAV.');return;}
  const attempt=++generation.current;setPhase('starting');setError('');setDraft(null);setSeconds(0);
  try{
   // Establish server-side authorization before asking for microphone access.
   await authorize();
   if(!mounted.current||attempt!==generation.current)return;
   const input=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1},video:false});
   if(!mounted.current||attempt!==generation.current){input.getTracks().forEach(track=>track.stop());return;}
   stream.current=input;discard.current=false;chunks.current=[];bytes.current=0;
   const capture=new MediaRecorder(input,{mimeType:type,audioBitsPerSecond:128000});recorder.current=capture;
   capture.ondataavailable=event=>{if(discard.current||!event.data.size)return;bytes.current+=event.data.size;if(bytes.current>MAX_BYTES){discard.current=true;chunks.current=[];if(capture.state==='recording')capture.stop();release();if(mounted.current){setError('Recording size limit reached. Try a shorter dictation.');setPhase('idle');}return;}chunks.current.push(event.data);};
   capture.onerror=()=>{discard.current=true;chunks.current=[];if(capture.state==='recording')capture.stop();release();if(mounted.current){setError('Microphone recording failed. Check the device and try again.');setPhase('idle');}};
   capture.onstop=()=>{
    release();if(!mounted.current||discard.current||attempt!==generation.current)return;
    const mime=type.split(';')[0],extension=mime==='audio/mp4'?'m4a':mime==='audio/ogg'?'ogg':'webm';
    const file=new File(chunks.current,`synthetic-dictation-${Date.now()}.${extension}`,{type:mime});chunks.current=[];
    if(!file.size||performance.now()-started.current<1000){setError('Record at least one second of speech before stopping.');setPhase('idle');return;}
    setDraft(file);void send(file);
   };
   input.getAudioTracks().forEach(track=>{track.onended=()=>{if(capture.state==='recording'&&!discard.current){discard.current=true;capture.stop();release();if(mounted.current){setError('The microphone disconnected. Start a new recording.');setPhase('idle');}}};});
   started.current=performance.now();capture.start(500);setPhase('recording');
   timer.current=window.setInterval(()=>{const elapsed=Math.floor((performance.now()-started.current)/1000);if(mounted.current)setSeconds(elapsed);if(elapsed>=MAX_SECONDS&&capture.state==='recording')capture.stop();},250);
  }catch(cause){release();if(!mounted.current||attempt!==generation.current)return;setPhase('idle');const name=cause instanceof DOMException?cause.name:'';setError(name==='NotAllowedError'?'Microphone permission was denied. Allow microphone access in the address bar, then try again.':name==='NotFoundError'?'No microphone was found. Connect one, or upload a recording.':name==='NotReadableError'?'The microphone is unavailable or in use by another app.':cause instanceof Error?cause.message:'Could not start the microphone.');}
 }
 return <section className="dictation" aria-labelledby="dictation-heading"><div className="dictation-heading"><div><span className="eyebrow">RECORD HERE</span><h3 id="dictation-heading">Microphone dictation</h3></div><span className={`dictation-timer ${phase==='recording'?'is-recording':''}`} role="timer" aria-label="Recording duration">{phase==='recording'&&<span className="recording-dot"/>}{formatTime(seconds)}</span></div>
 <p>Speak in English, then stop to get a local transcript. Text appears after processing. Maximum 5 minutes.</p>
 <label className="check"><input type="checkbox" checked={confirmed} disabled={active||phase==='sending'} onChange={event=>setConfirmed(event.target.checked)}/>I am dictating synthetic test speech, and recording and local-processing authorization is documented.</label>
 <p className="dictation-model">Local ASR: <strong>{profile||'No model configured'}</strong> · Development model; 5% WER requirement not met.</p>
 {!supported&&<p role="alert">Microphone capture requires a supported browser on localhost or HTTPS. You can still upload audio.</p>}
 {error&&<p role="alert" className="dictation-error">{error}</p>}
 <div className="dictation-controls">{active?<><button className="primary" disabled={phase==='starting'} onClick={()=>{if(recorder.current?.state==='recording')recorder.current.stop();}}>Stop & transcribe</button><button onClick={cancel}>Discard recording</button></>:<button className="primary" disabled={disabled||!confirmed||!supported||!profile||phase==='sending'} onClick={()=>void start()}>Start dictation</button>}
 {phase==='retry'&&draft&&<button disabled={disabled} onClick={()=>void send(draft)}>Retry recording upload</button>}</div>
 <p className="dictation-status" role="status" aria-live="polite">{phase==='starting'?'Authorizing and requesting microphone permission…':phase==='recording'?'Recording · microphone is on':phase==='sending'?'Processing your recording locally…':phase==='saved'?'Recording saved. Check the transcription result or job status below.':'The microphone is off.'}</p>
 {draft&&url&&<div className="dictation-preview"><audio controls src={url} aria-label="Dictation recording preview"/><a href={url} download={draft.name}>Save this recording locally</a></div>}
 </section>;
}
