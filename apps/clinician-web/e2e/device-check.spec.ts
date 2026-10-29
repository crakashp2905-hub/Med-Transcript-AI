import {test,expect} from '@playwright/test';
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
const token=JSON.parse(readFileSync(resolve('../..','data/local-config.json'),'utf8')).access_key;
test.use({permissions:['microphone'],launchOptions:{args:['--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream']}});
test('device identification releases tracks and stores or uploads no audio',async({page})=>{
 await page.addInitScript(()=>{const original=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);navigator.mediaDevices.getUserMedia=async constraints=>{const stream=await original(constraints);(window as unknown as {probeStream:MediaStream}).probeStream=stream;return stream;};});
 let uploads=0;page.on('request',request=>{if(request.method()==='POST'&&/\/(audio-uploads|stream-uploads)$/.test(request.url()))uploads++;});
 await page.goto('/');await page.getByLabel('Access key').fill(token);await page.getByRole('button',{name:'Open workspace',exact:false}).click();
 await page.getByRole('button',{name:'New encounter',exact:false}).click();await page.getByLabel('I confirmed the patient and encounter identifiers.').check();await page.getByRole('button',{name:'Create encounter',exact:false}).click();
 const button=page.getByRole('button',{name:'Identify microphone and check channels'});await expect(button).toBeDisabled();
 await page.getByLabel('I am dictating synthetic test speech, and recording and local-processing authorization is documented.').check();await button.click();
 await expect(page.getByText(/Microphone released/)).toBeVisible();
 expect(await page.evaluate(()=>(window as unknown as {probeStream:MediaStream}).probeStream.getTracks().every(t=>t.readyState==='ended'))).toBe(true);
 await page.getByRole('button',{name:'Check five-second microphone signal'}).click();
 await expect(page.getByText('Browser signal samples only.',{exact:false})).toBeVisible({timeout:15000});
 expect(await page.evaluate(()=>(window as unknown as {probeStream:MediaStream}).probeStream.getTracks().every(t=>t.readyState==='ended'))).toBe(true);
 expect(uploads).toBe(0);await expect(page.getByRole('button',{name:'Download device check'})).toBeVisible();
 await expect(page.getByRole('button',{name:'Prepare facts',exact:false})).toBeDisabled();
});

test('cancelled device check releases a late-granted microphone',async({page})=>{
 await page.addInitScript(()=>{const original=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);navigator.mediaDevices.getUserMedia=options=>new Promise<MediaStream>(resolve=>{(window as unknown as {grantProbe:()=>Promise<void>}).grantProbe=async()=>{const stream=await original(options);(window as unknown as {lateProbe:MediaStream}).lateProbe=stream;resolve(stream);};});});
 await page.goto('/');await page.getByLabel('Access key').fill(token);await page.getByRole('button',{name:'Open workspace',exact:false}).click();await page.getByRole('button',{name:'New encounter',exact:false}).click();await page.getByLabel('I confirmed the patient and encounter identifiers.').check();await page.getByRole('button',{name:'Create encounter',exact:false}).click();
 await page.getByLabel('I am dictating synthetic test speech, and recording and local-processing authorization is documented.').check();await page.getByRole('button',{name:'Identify microphone and check channels'}).click();
 await expect.poll(()=>page.evaluate(()=>!!(window as unknown as {grantProbe?:unknown}).grantProbe)).toBe(true);
 await page.getByRole('button',{name:'Cancel device check'}).click();await page.evaluate(()=>(window as unknown as {grantProbe:()=>Promise<void>}).grantProbe());
 await expect.poll(()=>page.evaluate(()=>(window as unknown as {lateProbe:MediaStream}).lateProbe.getTracks().every(t=>t.readyState==='ended'))).toBe(true);
 await expect(page.getByRole('button',{name:'Download device check'})).toHaveCount(0);
});
