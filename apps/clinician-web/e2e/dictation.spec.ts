import { test, expect, type Page } from '@playwright/test';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { resolve } from 'node:path';

const root=resolve('../..');
const token=process.env.MED_TRANSCRIPT_TEST_KEY||JSON.parse(readFileSync(resolve(root,'data/local-config.json'),'utf8')).access_key;
const fixture=resolve(root,'data/browser-fixtures/dictation.wav');
mkdirSync(resolve(root,'data/browser-fixtures'),{recursive:true});
// Public simulated speech, followed by silence. Chrome never accesses a real microphone.
const source=readFileSync(resolve(root,'evaluation/datasets/primock57-smoke-v1/day1_consultation01_patient.utterance03.wav'));
const padded=Buffer.concat([source,Buffer.alloc(16000*2*3)]);
padded.writeUInt32LE(padded.length-8,4);padded.writeUInt32LE(padded.length-44,40);writeFileSync(fixture,padded);
test.use({permissions:['microphone'],launchOptions:{args:[
 '--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream',`--use-file-for-fake-audio-capture=${fixture}`
]}});

async function encounter(page:Page){
 await page.goto('/');
 await page.getByLabel('Access key').fill(token);
 await page.getByRole('button',{name:'Open workspace',exact:false}).click();
 await page.getByRole('button',{name:'New encounter',exact:false}).click();
 await page.getByLabel('I confirmed the patient and encounter identifiers.').check();
 await page.getByRole('button',{name:'Create encounter',exact:false}).click();
 await expect(page.getByRole('heading',{name:'Microphone dictation'})).toBeVisible();
}

test('microphone dictation records, uploads, transcribes locally and leaves source review pending',async({page})=>{
 const failures:string[]=[];page.on('pageerror',error=>failures.push(error.message));
 await encounter(page);
 await expect(page.getByRole('button',{name:'Start dictation',exact:true})).toBeDisabled();
 await page.getByLabel('I am dictating synthetic test speech, and recording and local-processing authorization is documented.').check();
 await page.getByRole('button',{name:'Start dictation',exact:true}).click();
 await expect(page.getByText('Recording · microphone is on',{exact:true})).toBeVisible();
 await expect(page.getByRole('timer')).not.toHaveText('0:00',{timeout:4000});
 // Capture all 7.58 seconds of the synthetic utterance and a trailing silent interval.
 await page.waitForTimeout(9000);
 await page.getByRole('button',{name:'Stop & transcribe',exact:true}).click();
 await expect(page.getByLabel('Transcript segment 1')).toBeVisible({timeout:60000});
 await expect(page.getByLabel('Transcript segment 1')).toHaveValue(/vomit/i);
 await expect(page.getByRole('status')).toContainText('Dictation transcript ready');
 await expect(page.getByLabel('I confirmed supported English.')).not.toBeChecked();
 await expect(page.getByLabel('I reviewed source completeness.')).not.toBeChecked();
 await page.setViewportSize({width:390,height:844});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
 mkdirSync(resolve(root,'data/ui-screenshots'),{recursive:true});
 await page.screenshot({path:resolve(root,'data/ui-screenshots/dictation-result.png'),fullPage:true});
 expect(failures).toEqual([]);
});

test('discarding stops microphone tracks and sends no audio upload',async({page})=>{
 await page.addInitScript(()=>{
  const original=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
  navigator.mediaDevices.getUserMedia=async constraints=>{
   const stream=await original(constraints);(window as unknown as {testStream:MediaStream}).testStream=stream;return stream;
  };
 });
 let uploads=0;page.on('request',request=>{if(request.method()==='POST'&&/\/audio-uploads$/.test(request.url()))uploads++;});
 await encounter(page);
 await page.getByLabel('I am dictating synthetic test speech, and recording and local-processing authorization is documented.').check();
 await page.getByRole('button',{name:'Start dictation',exact:true}).click();
 await expect(page.getByText('Recording · microphone is on',{exact:true})).toBeVisible();
 await page.setViewportSize({width:390,height:844});
 await expect(page.locator('input[type=file]')).toBeDisabled();
 await expect(page.getByRole('button',{name:'New encounter',exact:false})).toBeDisabled();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
 await page.screenshot({path:resolve(root,'data/ui-screenshots/dictation-recording.png'),fullPage:true});
 await page.getByRole('button',{name:'Discard recording',exact:true}).click();
 await expect(page.getByText('The microphone is off.',{exact:true})).toBeVisible();
 expect(await page.evaluate(()=>(window as unknown as {testStream:MediaStream}).testStream.getTracks().every(track=>track.readyState==='ended'))).toBe(true);
 expect(uploads).toBe(0);
});

test('cancelling a pending microphone request stops a late-granted stream',async({page})=>{
 await page.addInitScript(()=>{
  const original=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
  navigator.mediaDevices.getUserMedia=async constraints=>{
   const stream=await original(constraints);
   const state=window as unknown as {testStream:MediaStream;releaseMicrophone:()=>void};state.testStream=stream;
   return new Promise<MediaStream>(resolve=>{state.releaseMicrophone=()=>resolve(stream);});
  };
 });
 await encounter(page);
 await page.getByLabel('I am dictating synthetic test speech, and recording and local-processing authorization is documented.').check();
 await page.getByRole('button',{name:'Start dictation',exact:true}).click();
 await expect.poll(()=>page.evaluate(()=>!!(window as unknown as {releaseMicrophone?:()=>void}).releaseMicrophone)).toBe(true);
 await page.getByRole('button',{name:'Discard recording',exact:true}).click();
 await page.evaluate(()=>(window as unknown as {releaseMicrophone:()=>void}).releaseMicrophone());
 await expect.poll(()=>page.evaluate(()=>(window as unknown as {testStream:MediaStream}).testStream.getTracks().every(track=>track.readyState==='ended'))).toBe(true);
 await expect(page.getByText('The microphone is off.',{exact:true})).toBeVisible();
});

test('microphone permission denial explains recovery without uploading audio',async({page})=>{
 await page.addInitScript(()=>{navigator.mediaDevices.getUserMedia=async()=>{throw new DOMException('Denied','NotAllowedError');};});
 await encounter(page);
 await page.getByLabel('I am dictating synthetic test speech, and recording and local-processing authorization is documented.').check();
 await page.getByRole('button',{name:'Start dictation',exact:true}).click();
 await expect(page.getByRole('alert')).toContainText('Microphone permission was denied');
 await expect(page.getByRole('button',{name:'Start dictation',exact:true})).toBeEnabled();
});

test('disconnected microphone retains a partial recording without automatic submission',async({page})=>{
 await page.addInitScript(()=>{
  const original=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
  navigator.mediaDevices.getUserMedia=async options=>{
   const stream=await original(options);(window as unknown as {testStream:MediaStream}).testStream=stream;return stream;
  };
 });
 let uploads=0;page.on('request',request=>{if(request.method()==='POST'&&/\/audio-uploads$/.test(request.url()))uploads++;});
 await encounter(page);
 await page.getByLabel('I am dictating synthetic test speech, and recording and local-processing authorization is documented.').check();
 await page.getByRole('button',{name:'Start dictation',exact:true}).click();
 await expect(page.getByText('Recording · microphone is on',{exact:true})).toBeVisible();
 await page.waitForTimeout(1600);
 await page.evaluate(()=>{const track=(window as unknown as {testStream:MediaStream}).testStream.getAudioTracks()[0];track.stop();track.dispatchEvent(new Event('ended'));});
 await expect(page.getByRole('alert')).toContainText('microphone disconnected');
 await expect(page.getByRole('link',{name:'Save this recording locally'})).toBeVisible();
 await expect(page.getByRole('button',{name:'Retry recording upload',exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'Start dictation',exact:true})).toBeDisabled();
 expect(uploads).toBe(0);
 await page.getByRole('button',{name:'Discard partial recording',exact:true}).click();
 await expect(page.getByRole('button',{name:'Start dictation',exact:true})).toBeEnabled();
});

test('simulated clock passes five minutes and stops capture at thirty minutes',async({page})=>{
 // Tests control timing, not a claim of 30 real minutes of browser-encoded audio.
 await page.clock.install();
 await encounter(page);
 await expect(page.getByText(/Maximum 30 minutes or 64 MiB/)).toBeVisible();
 await page.getByLabel('I am dictating synthetic test speech, and recording and local-processing authorization is documented.').check();
 await page.getByRole('button',{name:'Start dictation',exact:true}).click();
 await expect(page.getByText('Recording · microphone is on',{exact:true})).toBeVisible();
 await page.waitForTimeout(1500);
 await page.clock.fastForward(6*60*1000);
 await expect(page.getByText('Recording · microphone is on',{exact:true})).toBeVisible();
 await page.clock.fastForward(14*60*1000);
 await expect(page.getByText('Recording · microphone is on',{exact:true})).toBeVisible();
 await page.clock.fastForward(10*60*1000);
 await expect(page.getByText('Recording · microphone is on',{exact:true})).not.toBeVisible();
});

test('retry after a lost successful upload response reuses the saved source',async({page})=>{
 let puts=0,creationUrl='';const keys:string[]=[];
 page.on('request',request=>{if(request.method()==='POST'&&/\/audio-uploads$/.test(request.url())){creationUrl=request.url();keys.push(request.headers()['idempotency-key']);}});
 await page.route('**/audio-uploads/*/content',async route=>{puts++;await route.fetch();await route.abort('connectionreset');});
 await encounter(page);
 await page.getByLabel('I am dictating synthetic test speech, and recording and local-processing authorization is documented.').check();
 await page.getByRole('button',{name:'Start dictation',exact:true}).click();
 await expect(page.getByText('Recording · microphone is on',{exact:true})).toBeVisible();
 await page.waitForTimeout(2200);
 await page.getByRole('button',{name:'Stop & transcribe',exact:true}).click();
 await expect(page.getByRole('button',{name:'Retry recording upload',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Retry recording upload',exact:true}).click();
 await expect(page.getByLabel('Transcript segment 1').or(page.getByText('Recording saved. Check the transcription result or job status below.',{exact:true}))).toBeVisible({timeout:60000});
 expect(puts).toBe(1);expect(keys).toHaveLength(2);expect(keys[0]).toBe(keys[1]);
 const response=await page.request.get(creationUrl.replace('/audio-uploads','/uploads'),{headers:{Authorization:`Bearer ${token}`}});
 expect(response.ok()).toBe(true);expect((await response.json()).items).toHaveLength(1);
});
