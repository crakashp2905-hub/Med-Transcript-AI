import {test, expect, type Page, localTestKey, testOutputPath} from './fixtures/offline';
import { createHash, randomUUID } from 'node:crypto';
import { mkdirSync, readFileSync, unlinkSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

const root = resolve('../..');
const token=localTestKey;
const fixture = testOutputPath(`data/browser-fixtures/complete-consultation-${randomUUID()}.wav`);
mkdirSync(resolve(fixture, '..'), { recursive: true });
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
  await page.getByLabel('Note template').selectOption({ label: 'SOAP with follow-up' });
  await expect(page.getByRole('heading', { name: 'Follow Up' })).toBeVisible();
  await page.getByLabel('Add a note section').fill('Additional findings');
  await page.getByRole('button', { name: 'Add section', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Additional Findings' })).toBeVisible();
  const correctionCard = cards.first();
  for (let index = 0; index < await cards.count(); index++) {
    const card = cards.nth(index);
    await card.getByRole('combobox', { name: 'Subject', exact: true }).selectOption('patient');
    await card.getByRole('combobox', { name: 'Temporality', exact: true }).selectOption('current');
    await card.getByLabel('Content and attribution reviewed').check();
    await card.getByLabel('Critical details checked').check();
  }
  await page.getByRole('button', { name: 'Save & verify note', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Note preview' })).toBeVisible();

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

  for (const format of ['markdown', 'text', 'fhir'] as const) {
    const labels = { markdown: 'Markdown', text: 'Text', fhir: 'Fhir' } as const;
    const extensions = { markdown: 'md', text: 'txt', fhir: 'json' } as const;
    const event = page.waitForEvent('download');
    await page.getByRole('button', { name: `↓ ${labels[format]}`, exact: true }).click();
    const documentDownload = await event;
    expect(documentDownload.suggestedFilename()).toContain(`.${extensions[format]}`);
    const documentPath = testInfo.outputPath(`approved-note.${format}.${extensions[format]}`);
    await documentDownload.saveAs(documentPath);
    if (format === 'markdown') {
      const rendered = readFileSync(documentPath, 'utf8');
      expect(rendered).toContain('# Approved clinical note');
      expect(rendered).toContain('Source transcript:');
      expect(rendered).toContain('## Follow Up');
      expect(rendered).toContain('## Additional Findings');
    } else if (format === 'text') {
      const rendered = readFileSync(documentPath, 'utf8');
      expect(rendered).toContain('APPROVED CLINICAL NOTE');
      expect(rendered).toContain('Source transcript:');
    } else {
      const rendered = JSON.parse(readFileSync(documentPath, 'utf8'));
      expect(rendered.resourceType).toBe('DocumentReference');
      expect(rendered.docStatus).toBe('final');
    }
    await testInfo.attach(`approved-note.${format}`, {
      path: documentPath,
      contentType: format === 'markdown' ? 'text/markdown' : format === 'text' ? 'text/plain' : 'application/fhir+json',
    });
  }

  for (const format of ['pdf', 'docx'] as const) {
    const event = page.waitForEvent('download');
    await page.getByRole('button', { name: `↓ ${format.toUpperCase()}`, exact: true }).click();
    const documentDownload = await event;
    expect(documentDownload.suggestedFilename()).toContain(`.${format}`);
    const documentPath = testInfo.outputPath(`approved-note.${format}`);
    await documentDownload.saveAs(documentPath);
    const bytes = readFileSync(documentPath);
    expect(format === 'pdf' ? bytes.subarray(0, 8).toString() : bytes.subarray(0, 2).toString()).toBe(
      format === 'pdf' ? '%PDF-1.4' : 'PK',
    );
    await testInfo.attach(`approved-note.${format}`, {
      path: documentPath,
      contentType: format === 'pdf' ? 'application/pdf' : 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    });
  }
  expect(errors).toEqual([]);
});
