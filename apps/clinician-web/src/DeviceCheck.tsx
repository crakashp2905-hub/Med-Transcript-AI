import {useEffect,useRef,useState} from 'react';
type Report={schema_version:string;device_label:string;requested_channels:number;reported_channels:number|null;reported_sample_rate:number|null;channel_capabilities:unknown;requested_count_reported:boolean;physical_routing_validated:false;clinical_speaker_validation:false;audio_stored:false};
export function DeviceCheck({device,channels,disabled,authorize,onChecking}:{device:string;channels:number;disabled:boolean;authorize:()=>Promise<void>;onChecking:(checking:boolean)=>void}){
 const [checking,setChecking]=useState(false),[report,setReport]=useState<Report|null>(null),[error,setError]=useState('');
 const generation=useRef(0),mounted=useRef(true),input=useRef<MediaStream|null>(null);
 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;generation.current++;input.current?.getTracks().forEach(t=>t.stop());};},[]);
 function finish(){input.current?.getTracks().forEach(t=>t.stop());input.current=null;if(mounted.current){setChecking(false);onChecking(false);}}
 async function check(){const attempt=++generation.current;setChecking(true);onChecking(true);setReport(null);setError('');
  try{await authorize();if(!mounted.current||attempt!==generation.current)return;
   const stream=await navigator.mediaDevices.getUserMedia({audio:{...(device?{deviceId:{exact:device}}:{}),channelCount:{exact:channels},echoCancellation:false,noiseSuppression:false,autoGainControl:false},video:false});
   if(!mounted.current||attempt!==generation.current){stream.getTracks().forEach(t=>t.stop());return;}input.current=stream;
   const track=stream.getAudioTracks()[0],settings=track.getSettings();let capabilities:MediaTrackCapabilities={};try{capabilities=track.getCapabilities();}catch{}
   setReport({schema_version:'browser_device_capability_check_v1',device_label:track.label||'Unnamed input',requested_channels:channels,reported_channels:settings.channelCount??null,reported_sample_rate:settings.sampleRate??null,channel_capabilities:capabilities.channelCount??null,requested_count_reported:settings.channelCount===channels,physical_routing_validated:false,clinical_speaker_validation:false,audio_stored:false});
  }catch{if(mounted.current&&attempt===generation.current)setError('The input could not confirm the requested configuration. Allow microphone access, choose fewer channels or use a compatible interface.');}
  finally{if(attempt===generation.current)finish();}
 }
 function cancel(){generation.current++;finish();}
 function download(){if(!report)return;const url=URL.createObjectURL(new Blob([JSON.stringify(report,null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='microphone-capability-check.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
 return <section aria-label="Microphone device check"><p>Identify your input before recording. This briefly opens the microphone to read its reported settings; no audio is stored. Confirm the synthetic recording authorization below first.</p><button disabled={disabled||checking} onClick={()=>void check()}>Identify microphone and check channels</button>{checking&&<button onClick={cancel}>Cancel device check</button>}{error&&<p role="alert">{error}</p>}{report&&<><p role="status">Input: {report.device_label}. Requested {report.requested_channels}; reported {report.reported_channels??'unknown'} channels, sample rate {report.reported_sample_rate??'unknown'} Hz. Microphone released.</p><p>{report.requested_count_reported?'The browser reports the requested channel count.':'The requested channel count is unconfirmed.'} Actual routing, cross-talk and timing still require a controlled recording and human observation.</p><button onClick={download}>Download device check</button></>}</section>;
}
