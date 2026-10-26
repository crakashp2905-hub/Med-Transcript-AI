// Physical channels from one synchronized device. Never combine independent device clocks.
export type Capture = {-readonly [K in 'state'|'start'|'stop'|'ondataavailable'|'onerror'|'onstop']:MediaRecorder[K]};
export async function pcmCapture(input:MediaStream,count:number,onLimit:(reason?:string)=>void):Promise<Capture>{
 const context=new AudioContext({sampleRate:16000});
 let node:AudioWorkletNode|undefined;
 let batch:Int16Array[]=[];let batchSamples=0,samples=0,closed=false;
 const close=()=>{node?.disconnect();source.disconnect();void context.close();};
 if(context.sampleRate!==16000){void context.close();throw new Error('This browser cannot capture 16 kHz PCM. Upload a recording instead.');}
 const source=context.createMediaStreamSource(input);
 try{await context.audioWorklet.addModule('/assets/pcm-worklet.js');}catch(error){close();throw error;}
 const capture={state:'inactive',ondataavailable:null,onerror:null,onstop:null,start(){capture.state='recording';void context.resume();},stop(){
  if(closed)return;closed=true;capture.state='inactive';close();
  flush();queueMicrotask(()=>capture.onstop?.call(capture as unknown as MediaRecorder,new Event('stop')));
 }} as Capture;
 function flush(){if(!batchSamples)return;const data=new Blob(batch.map(c=>c.buffer as ArrayBuffer),{type:'application/octet-stream'});batch=[];batchSamples=0;capture.ondataavailable?.call(capture as unknown as MediaRecorder,new BlobEvent('dataavailable',{data}));}
 node=new AudioWorkletNode(context,'scribe-pcm',{channelCount:count,channelCountMode:count===1?'explicit':'max',channelInterpretation:count===1?'speakers':'discrete',numberOfInputs:1,numberOfOutputs:1,outputChannelCount:[count]});
 node.port.onmessage=event=>{
  if(capture.state!=='recording')return;
  const channels=event.data as Float32Array[];
  if(channels.length!==count){onLimit('The browser changed the input channel count. Capture stopped to avoid mixing or fabricating channels.');capture.stop();return;}
  const length=channels[0].length;
  if((samples+length*count)*2+44>511999956){onLimit();capture.stop();return;}
  const pcm=new Int16Array(length*count);for(let i=0;i<length;i++)for(let c=0;c<count;c++){const x=Math.max(-1,Math.min(1,channels[c][i]));pcm[i*count+c]=Math.round(x*(x<0?32768:32767));}batch.push(pcm);batchSamples+=pcm.length;samples+=pcm.length;if(batchSamples>=8000*count)flush();
 };
 node.onprocessorerror=()=>{onLimit();capture.stop();};
 const mute=context.createGain();mute.gain.value=0;source.connect(node);node.connect(mute);mute.connect(context.destination);
 return capture;
}
