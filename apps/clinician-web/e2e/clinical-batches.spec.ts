import {test,expect} from '@playwright/test';
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
const token=JSON.parse(readFileSync(resolve('../..','data/local-config.json'),'utf8')).access_key;
test('long source proposal batches preserve earlier editor selections and require review',async({page})=>{
 const headers={Authorization:`Bearer ${token}`};
 const demo=await page.request.post('/v1/demo',{headers});expect(demo.ok()).toBe(true);const eid=(await demo.json()).encounter_id;
 const workspace=await(await page.request.get(`/v1/encounters/${eid}/workspace`,{headers})).json();
 const source=await page.request.post(`/v1/encounters/${eid}/manual-transcripts`,{headers,data:{audio_asset_id:workspace.transcript.audio_asset_id,segments:Array.from({length:25},(_,i)=>({start_ms:i*100,end_ms:i*100+90,text:`Patient reports cough ${i}.`,role:'unknown'}))}});expect(source.ok()).toBe(true);
 const batches:string[][]=[];
 // Use the real scoped API and deterministic provider to test UI batching without
 // competing with the independently running full ASR benchmark.
 await page.route('**/fact-proposals',async route=>{const body=route.request().postDataJSON();batches.push(body.segment_ids);const response=await route.fetch({postData:{...body,mode:'rules'}});await route.fulfill({response});});
 await page.goto('/');await page.getByLabel('Access key').fill(token);await page.getByRole('button',{name:'Open workspace',exact:false}).click();await page.locator('.encounter-item').first().click();await page.getByRole('button',{name:'Facts & SOAP note',exact:false}).click();
 await page.getByRole('button',{name:'Propose next 20 source segments with local model'}).click();
 await expect(page.getByText('20 of 25 source segments processed.',{exact:false})).toBeVisible();
 await page.getByText('Review 20 source-span proposals in this batch',{exact:true}).click();
 let region=page.getByRole('region',{name:'Select source-linked clinical proposals'});await region.getByRole('checkbox').first().check();await region.getByRole('button',{name:'Add selected unreviewed proposals'}).click();
 await expect(page.locator('.fact-card')).toHaveCount(1);
 await page.getByRole('button',{name:'Propose next 5 source segments with local model'}).click();
 await expect(page.getByText('25 of 25 source segments processed.',{exact:false})).toBeVisible();await page.getByText('Review 5 source-span proposals in this batch',{exact:true}).click();
 region=page.getByRole('region',{name:'Select source-linked clinical proposals'});await region.getByRole('checkbox').first().check();await region.getByRole('button',{name:'Add selected unreviewed proposals'}).click();
 await expect(page.locator('.fact-card')).toHaveCount(2);expect(batches.map(b=>b.length)).toEqual([20,5]);expect(new Set(batches.flat()).size).toBe(25);
 for(const checkbox of await page.getByLabel('Content and attribution reviewed').all())await expect(checkbox).not.toBeChecked();
 const final=await(await page.request.get(`/v1/encounters/${eid}/workspace`,{headers})).json();expect(final.note).toBeNull();expect(final.approval).toBeNull();
});
