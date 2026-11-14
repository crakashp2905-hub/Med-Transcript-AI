import { test, expect, type Page } from './fixtures/offline';
import { createHash, randomUUID } from 'node:crypto';
import { mkdirSync, readFileSync, unlinkSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

const root = resolve('../..');
const token = process.env.MED_TRANSCRIPT_TEST_KEY ||
  JSON.parse(readFileSync(resolve(root, 'data/local-config.json'), 'utf8')).access_key;
const fixture = resolve(root, `data/browser-fixtures/complete-consultation-${randomUUID()}.wav`);
mkdirSync(resolve(root, 'data/browser-fixtures'), { recursive: true });
const sourcePath = resolve(
  root,
  'evaluation/datasets/primock57-smoke-v1/day1_consultation01_patient.utterance03.wav',
);
const source = readFileSync(sourcePath);
const datasetManifest = JSON.parse(readFileSync(
  resolve(root, 'evaluation/datasets/primock57-smoke-v1/manifest.json'), 'utf8',
));
const sourceSample = datasetManifest.samples.find(
  (sample: { sample_id: string }) => sample.sample_id === 'day1_consultation01_patient.utterance03',
);
if (!sourceSample || createHash('sha256').update(source).digest('hex') !== sourceSample.audio_sha256) {
  throw new Error('synthetic_fixture_manifest_integrity_failed');
}
const padded = Buffer.concat([source, Buffer.alloc(16000 * 2 * 3)]);
padded.writeUInt32LE(padded.length - 8, 4);
padded.writeUInt32LE(padded.length - 44, 40);
writeFileSync(fixture, padded);

test.afterAll(() => unlinkSync(fixture));
test.use({
  permissions: ['microphone'],
  launchOptions: { args: [
    '--use-fake-ui-for-media-stream',
    '--use-fake-device-for-media-stream',
    `--use-file-for-fake-audio-capture=${fixture}`,
  ] },
});

async function createEncounter(page: Page) {
  await page.goto('/');
  await page.getByLabel('Access key').fill(token);
  await page.getByRole('button', { name: 'Open workspace', exact: false }).click();
  await page.getByRole('button', { name: 'New encounter', exact: false }).click();
  await page.getByLabel('I confirmed the patient and encounter identifiers.').check();
  await page.getByRole('button', { name: 'Create encounter', exact: false }).click();
  await expect(page.getByRole('heading', { name: 'Microphone dictation' })).toBeVisible();
}

test('one synthetic consultation completes capture, review, approval, and JSON export', async ({ page }, testInfo) => {
  test.setTimeout(180000);
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await createEncounter(page);
  await page.getByLabel('I am dictating synthetic test speech, and recording and local-processing authorization is documented.').check();
  await page.getByRole('button', { name: 'Start dictation', exact: true }).click();
  await expect(page.getByText('Recording · microphone is on', { exact: true })).toBeVisible();
  await page.waitForTimeout(9000);
  await page.getByRole('button', { name: 'Stop & transcribe', exact: true }).click();
  await expect(page.getByLabel('Transcript segment 1')).toBeVisible({ timeout: 120000 });
  await expect(page.getByLabel('Transcript segment 1')).toHaveValue(/vomit/i);

  await page.getByLabel('Speaker role 1').selectOption('patient');
  await page.getByLabel('I confirmed supported English.').check();
  await page.getByLabel('I reviewed source completeness.').check();
  await page.getByLabel('Review basis').fill('Reviewed the complete scripted synthetic recording.');
  await page.getByLabel('Correction reason').fill('Reviewed the scripted transcript and confirmed its source coverage.');
  await page.getByRole('button', { name: 'Save source review', exact: true }).click();
  await expect(page.locator('.notice')).toContainText('Saved as a new source version');

  await page.getByRole('button', { name: 'Prepare facts', exact: false }).click();
  const cards = page.locator('.fact-card');
  await expect(cards.first()).toBeVisible();
  const correctionCard = cards.first();
  for (let index = 0; index < await cards.count(); index++) {
    const card = cards.nth(index);
    await card.getByRole('combobox', { name: 'Subject', exact: true }).selectOption('patient');
    await card.getByRole('combobox', { name: 'Temporality', exact: true }).selectOption('current');
    await card.getByLabel('Content and attribution reviewed').check();
    await card.getByLabel('Critical details checked').check();
  }
  await page.getByRole('button', { name: 'Save & verify note', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'SOAP preview' })).toBeVisible();

  const noteField = correctionCard.getByLabel('Note statement');
  const initialDraft = await noteField.inputValue();
  await noteField.fill(initialDraft.endsWith('.') ? initialDraft.slice(0, -1) : `${initialDraft}.`);
  await correctionCard.getByLabel('Clinical clarification / exclusion reason').fill(
    'Synthetic punctuation-only correction; clinical meaning is unchanged.'
  );
  await page.getByRole('button', { name: 'Save & verify note', exact: true }).click();
  await expect(page.getByText('Saved a new note version and verification report.')).toBeVisible();
  await expect(page.locator('.review-side')).toContainText('structured field disagreement');
  const approve = page.getByRole('button', { name: 'Approve saved version', exact: false });
  await expect(approve).toBeDisabled();

  await correctionCard.getByLabel('Note statement').fill(
    'Patient vomited at the start of symptoms; vomiting has now stopped.',
  );
  await correctionCard.getByRole('combobox', { name: 'Category', exact: true }).selectOption('symptom');
  await correctionCard.getByRole('combobox', { name: 'Temporality', exact: true }).selectOption('historical');
  await correctionCard.getByLabel('Clinical clarification / exclusion reason').fill(
    'Synthetic test correction: classify the supported past symptom and its documented resolution.',
  );
  await correctionCard.getByLabel('Content and attribution reviewed').check();
  await correctionCard.getByLabel('Critical details checked').check();
  await page.getByRole('button', { name: 'Save & verify note', exact: true }).click();
  await expect(page.locator('.review-side')).toContainText('omitted source terms');
  await correctionCard.getByRole('button', { name: 'Record as clinician addition' }).click();
  await expect(page.locator('.review-side')).toContainText('Manual additions without transcript evidence:');
  await expect(page.getByRole('heading', { name: 'Ready for your final review' })).toBeVisible();

  await expect(page.getByRole('region', { name: 'Source alongside note' })).toContainText('vomiting');
  await page.getByLabel('I rechecked the patient identifiers and the exact saved note.').check();
  await expect(approve).toBeEnabled();
  await approve.click();
  await expect(page.getByRole('heading', { name: 'Approved record' })).toBeVisible();

  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: '↓ Json', exact: true }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toContain('.json');
  const exportPath = testInfo.outputPath('approved-note.json');
  mkdirSync(resolve(exportPath, '..'), { recursive: true });
  await download.saveAs(exportPath);
  await testInfo.attach('approved-note.json', { path: exportPath, contentType: 'application/json' });
  const exported = JSON.parse(readFileSync(exportPath, 'utf8'));
  expect(exported.approval).toBeDefined();
  expect(exported.note).toBeDefined();
  expect(errors).toEqual([]);
});
