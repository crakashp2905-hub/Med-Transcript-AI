// Physical channels from one synchronized device. Never combine independent device clocks.
export type Capture = {-readonly [K in 'state'|'start'|'stop'|'ondataavailable'|'onerror'|'onstop']:MediaRecorder[K]};
export async function pcmCapture(input:MediaStream,count:number,onLimit:(reason?:string)=>void):Promise<Capture>{
 const context=new AudioContext({sampleRate:16000});
 let node:AudioWorkletNode|undefined;
 const chunks:Int16Array[]=[];let samples=0,closed=false;
 const close=()=>{node?.disconnect();source.disconnect();void context.close();};
 const source=context.createMediaStreamSource(input);
 try{await context.audioWorklet.addModule('/assets/pcm-worklet.js');}catch(error){close();throw error;}
 const capture={state:'inactive',ondataavailable:null,onerror:null,onstop:null,start(){capture.state='recording';void context.resume();},stop(){
  if(closed)return;closed=true;capture.state='inactive';close();
  const header=new ArrayBuffer(44),v=new DataView(header),str=(at:number,s:string)=>{for(let i=0;i<s.length;i++)v.setUint8(at+i,s.charCodeAt(i));};
  str(0,'RIFF');v.setUint32(4,36+samples*2,true);str(8,'WAVE');str(12,'fmt ');v.setUint32(16,16,true);v.setUint16(20,1,true);v.setUint16(22,count,true);v.setUint32(24,context.sampleRate,true);v.setUint32(28,context.sampleRate*count*2,true);v.setUint16(32,count*2,true);v.setUint16(34,16,true);str(36,'data');v.setUint32(40,samples*2,true);
  const data=new Blob([header,...chunks.map(c=>c.buffer as ArrayBuffer)],{type:'audio/wav'});chunks.length=0;
  queueMicrotask(()=>{capture.ondataavailable?.call(capture as unknown as MediaRecorder,new BlobEvent('dataavailable',{data}));capture.onstop?.call(capture as unknown as MediaRecorder,new Event('stop'));});
 }} as Capture;
 node=new AudioWorkletNode(context,'scribe-pcm',{channelCount:count,channelCountMode:'max',channelInterpretation:'discrete',numberOfInputs:1,numberOfOutputs:1,outputChannelCount:[count]});
 node.port.onmessage=event=>{
  if(capture.state!=='recording')return;
  const channels=event.data as Float32Array[];
  if(channels.length!==count){onLimit('The browser changed the input channel count. Capture stopped to avoid mixing or fabricating channels.');capture.stop();return;}
  const length=channels[0].length;
  if((samples+length*count)*2+44>64*1024*1024){onLimit();capture.stop();return;}
  const pcm=new Int16Array(length*count);for(let i=0;i<length;i++)for(let c=0;c<count;c++){const x=Math.max(-1,Math.min(1,channels[c][i]));pcm[i*count+c]=Math.round(x*(x<0?32768:32767));}chunks.push(pcm);samples+=pcm.length;
 };
 node.onprocessorerror=()=>{onLimit();capture.stop();};
 const mute=context.createGain();mute.gain.value=0;source.connect(node);node.connect(mute);mute.connect(context.destination);
 return capture;
}
