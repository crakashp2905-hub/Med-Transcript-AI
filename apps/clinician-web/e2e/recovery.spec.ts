import {test,expect,type Page} from '@playwright/test';
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
const root=resolve('../..');
const token=process.env.MED_TRANSCRIPT_TEST_KEY||JSON.parse(readFileSync(resolve(root,'data/local-config.json'),'utf8')).access_key;
const fixture=resolve(root,'evaluation/datasets/primock57-smoke-v1/day1_consultation01_patient.utterance03.wav');
test.use({permissions:['microphone'],launchOptions:{args:['--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream',`--use-file-for-fake-audio-capture=${fixture}`]}});
async function login(page:Page){await page.goto('/');await page.getByLabel('Access key').fill(token);await page.getByRole('button',{name:'Open workspace',exact:false}).click();}
async function create(page:Page){await page.getByRole('button',{name:'New encounter',exact:false}).click();await page.getByLabel('I confirmed the patient and encounter identifiers.').check();await page.getByRole('button',{name:'Create encounter',exact:false}).click();await expect(page.getByRole('heading',{name:'Microphone dictation'})).toBeVisible();}
async function record(page:Page){await page.getByLabel('I am dictating synthetic test speech, and recording and local-processing authorization is documented.').check();await page.getByRole('button',{name:'Start dictation',exact:true}).click();await expect(page.getByText('Recording · microphone is on',{exact:true})).toBeVisible();}

test('reload recovers committed audio only in its encounter, with explicit retry and deletion',async({page})=>{
 let uploads=0;page.on('request',request=>{if(request.method()==='POST'&&/\/audio-uploads$/.test(request.url()))uploads++;});
 await login(page);await create(page);await record(page);await page.waitForTimeout(2200);
 await expect.poll(()=>page.evaluate(async()=>{return new Promise<number>(resolve=>{const r=indexedDB.open('med-transcript-recordings-v1');r.onsuccess=()=>{const db=r.result,q=db.transaction('drafts').objectStore('drafts').getAll();q.onsuccess=()=>{resolve(q.result.reduce((sum,row)=>sum+row.bytes,0));db.close();};};});})).toBeGreaterThan(0);
 page.on('dialog',dialog=>void dialog.accept());await page.reload();await page.getByLabel('Access key').fill(token);await page.getByRole('button',{name:'Open workspace',exact:false}).click();
 await create(page);await expect(page.getByRole('region',{name:'Unfinished recordings'})).toHaveCount(0);
 await page.locator('.encounter-item').nth(1).click();
 await expect(page.getByRole('button',{name:'Recover unfinished recording'})).toBeVisible();
 await page.getByRole('button',{name:'Recover unfinished recording'}).click();
 await expect(page.getByRole('link',{name:'Save this recording locally'})).toBeVisible();
 await expect(page.getByRole('button',{name:'Retry recording upload'})).toBeDisabled();expect(uploads).toBe(0);
 await page.getByRole('button',{name:'Discard partial recording'}).click();
 await expect(page.getByRole('button',{name:'Recover unfinished recording'})).toHaveCount(0);
});

test('storage quota failure stops capture and retains previously committed audio',async({page})=>{
 await page.addInitScript(()=>{const add=IDBObjectStore.prototype.add;IDBObjectStore.prototype.add=function(value,key){if(this.name==='parts'&&(window as unknown as {quotaFailure:boolean}).quotaFailure)throw new DOMException('Test storage quota','QuotaExceededError');return key===undefined?add.call(this,value):add.call(this,value,key);};});
 await login(page);await create(page);await record(page);await page.waitForTimeout(1800);
 await page.evaluate(()=>{(window as unknown as {quotaFailure:boolean}).quotaFailure=true;});
 await expect(page.getByRole('alert')).toContainText('Browser storage failed or is full');
 await expect(page.getByRole('button',{name:'Retry recording upload'})).toBeVisible();
 await expect(page.getByRole('link',{name:'Save this recording locally'})).toBeVisible();
 await page.getByRole('button',{name:'Discard partial recording'}).click();
});


test('large upload resumes after a lost chunk response without retransmitting committed bytes',async({page})=>{
 const size=9*1024*1024+44,content=Buffer.alloc(size);content.write('RIFF',0);content.writeUInt32LE(size-8,4);content.write('WAVEfmt ',8);content.writeUInt32LE(16,16);content.writeUInt16LE(1,20);content.writeUInt16LE(1,22);content.writeUInt32LE(16000,24);content.writeUInt32LE(32000,28);content.writeUInt16LE(2,32);content.writeUInt16LE(16,34);content.write('data',36);content.writeUInt32LE(size-44,40);
 const offsets:number[]=[];let interrupted=false;
 await page.route('**/audio-uploads/*/content',async route=>{if(route.request().method()!=='PATCH'){await route.continue();return;}const offset=Number(route.request().headers()['upload-offset']);offsets.push(offset);if(!interrupted){interrupted=true;await route.fetch();await route.abort('connectionreset');}else await route.continue();});
 await login(page);await create(page);
 await page.locator('input[type=file]').setInputFiles({name:'resumable-public-transport.wav',mimeType:'audio/wav',buffer:content});
 await page.getByLabel('Recording and local-processing authorization is documented.',{exact:true}).check();
 await page.getByRole('button',{name:'Upload recording',exact:true}).click();
 await expect.poll(()=>offsets.length).toBe(1);
 await expect(page.getByRole('button',{name:'Upload recording',exact:true})).toBeEnabled();
 await page.getByRole('button',{name:'Upload recording',exact:true}).click();
 await expect(page.locator('.notice')).toContainText('Recording received');
 expect(offsets).toEqual([0,4*1024*1024,8*1024*1024]);
});

test('live local preview is labelled provisional and does not prepare or approve a note',async({page})=>{
 let eid='',previews=0;
 page.on('request',request=>{const match=request.url().match(/\/encounters\/([^/]+)\/audio-uploads$/);if(match)eid=match[1];});
 await page.route('**/transcriptions',async route=>{const body=route.request().postDataJSON();if(!body.preview_only){await route.continue();return;}previews++;await route.fulfill({status:202,json:{job_id:'test-preview',status_url:'/v1/jobs/test-preview'}});});
 await page.route('**/v1/jobs/test-preview',route=>route.fulfill({status:200,json:{status:'succeeded',result:{approvable:false,provisional_segments:[{start_ms:0,end_ms:1000,text:'Synthetic provisional preview.'}]}}}));
 await login(page);await create(page);await page.getByLabel('Show provisional local previews while recording').check();await record(page);
 await expect(page.getByText('Synthetic provisional preview.',{exact:false})).toBeVisible({timeout:45000});
 await expect(page.getByRole('heading',{name:'PROVISIONAL · NOT A SAVED TRANSCRIPT'})).toBeVisible();
 await expect(page.getByText('Recording · microphone is on',{exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'Prepare facts',exact:false})).toBeDisabled();
 await page.getByRole('button',{name:'Discard recording'}).click();expect(previews).toBeGreaterThan(0);
 const response=await page.request.get(`/v1/encounters/${eid}/workspace`,{headers:{Authorization:`Bearer ${token}`}});const ws=await response.json();expect(ws.transcript).toBeNull();expect(ws.note).toBeNull();expect(ws.approval).toBeNull();
});


test('late rejection from cancelled microphone request cannot stop a newer capture',async({page})=>{
 await page.addInitScript(()=>{const original=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);let calls=0;navigator.mediaDevices.getUserMedia=async options=>{calls++;if(calls===1)return new Promise<MediaStream>((_,reject)=>{(window as unknown as {rejectOld:()=>void}).rejectOld=()=>reject(new DOMException('Late denial','NotAllowedError'));});const stream=await original(options);(window as unknown as {newStream:MediaStream}).newStream=stream;return stream;};});
 await login(page);await create(page);await page.getByLabel('I am dictating synthetic test speech, and recording and local-processing authorization is documented.').check();await page.getByRole('button',{name:'Start dictation',exact:true}).click();
 await expect.poll(()=>page.evaluate(()=>!!(window as unknown as {rejectOld?:()=>void}).rejectOld)).toBe(true);
 await page.getByRole('button',{name:'Discard recording'}).click();await page.getByRole('button',{name:'Start dictation',exact:true}).click();
 await expect(page.getByText('Recording · microphone is on',{exact:true})).toBeVisible();
 await page.evaluate(()=>(window as unknown as {rejectOld:()=>void}).rejectOld());await page.waitForTimeout(300);
 await expect(page.getByText('Recording · microphone is on',{exact:true})).toBeVisible();
 expect(await page.evaluate(()=>(window as unknown as {newStream:MediaStream}).newStream.getTracks().every(t=>t.readyState==='live'))).toBe(true);
 await page.getByRole('button',{name:'Discard recording'}).click();
});

test('revoked recording permission stops capture and requires fresh confirmation',async({page})=>{
 await page.route('**/processing-permission',route=>route.fulfill({status:200,json:{recording_authorized:false,local_processing_authorized:false}}));
 await login(page);await create(page);await record(page);
 await expect(page.getByRole('alert')).toContainText('Recording authorization is inactive',{timeout:12000});
 await expect(page.getByRole('button',{name:'Retry recording upload'})).toBeDisabled();
 await expect(page.getByRole('link',{name:'Save this recording locally'})).toBeVisible();
 await page.getByRole('button',{name:'Discard partial recording'}).click();
});
