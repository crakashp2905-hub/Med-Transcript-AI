import {test,expect} from './fixtures/offline';
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';

const token=JSON.parse(readFileSync(resolve('../..','data/local-config.json'),'utf8')).access_key;

test('uncertain source queue renders a source-bound waveform and selected interval',async({page})=>{
 await page.route('**/waveform**',route=>route.fulfill({json:{peaks:Array.from({length:160},(_,index)=>0.2+(index%7)/10)}}));
 await page.route('**/v1/encounters/*/workspace',async route=>{
  const response=await route.fetch();const body=await response.json();
  if(body.transcript?.segments?.length)body.transcript.segments[0].uncertainties=['unreviewed_asr'];
  await route.fulfill({response,json:body});
 });
 await page.goto('/');
 await page.getByLabel('Access key').fill(token);
 await page.getByRole('button',{name:'Open workspace',exact:false}).click();
 await page.getByRole('button',{name:'Open synthetic example',exact:false}).click();
 const queue=page.getByRole('region',{name:'Uncertain source spans'});
 const waveform=queue.getByRole('img',{name:/Audio waveform with selected interval/}).first();
 await expect(waveform).toBeVisible();
 await expect(waveform.locator('line.waveform-peak')).toHaveCount(160);
 await expect(waveform.locator('rect.waveform-selection')).toHaveAttribute('width',/.+/);
});
