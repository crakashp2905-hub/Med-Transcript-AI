import {test,expect,localTestKey} from './fixtures/offline';

async function openCapture(page: import('@playwright/test').Page) {
 await page.goto('/');
 await page.getByLabel('Access key').fill(localTestKey);
 await page.getByRole('button',{name:'Open workspace',exact:false}).click();
 await page.getByRole('button',{name:'New encounter',exact:false}).click();
 await page.getByLabel('I confirmed the patient and encounter identifiers.').check();
 await page.getByRole('button',{name:'Create encounter',exact:false}).click();
 await expect(page.getByRole('heading',{name:'Microphone dictation'})).toBeVisible();
}

test('first-run model readiness verifies pinned files without loading or running ASR',async({page})=>{
 await openCapture(page);
 const readiness=page.getByRole('region',{name:'Local ASR model readiness'});
 await page.getByRole('button',{name:'Check local model files'}).click();
 await expect(readiness.getByRole('status')).toContainText('Model files and SHA-256 hashes verified.');
 await expect(readiness.getByRole('status')).toContainText('model was not loaded');
 await expect(readiness.getByRole('status')).toContainText('ASR accuracy admission is not established');
});

test('model readiness failure explains retry and manual transcription fallback',async({page})=>{
 await page.route('**/v1/asr-profiles/**/readiness',route=>route.fulfill({status:503,contentType:'application/json',body:'{"detail":"readiness_unavailable"}'}));
 await openCapture(page);
 const readiness=page.getByRole('region',{name:'Local ASR model readiness'});
 await page.getByRole('button',{name:'Check local model files'}).click();
 await expect(readiness.getByRole('alert')).toContainText('Could not verify local model files.');
 await expect(readiness.getByRole('alert')).toContainText('manual transcription');
 await expect(page.getByRole('button',{name:'Check local model files'})).toBeEnabled();
});
