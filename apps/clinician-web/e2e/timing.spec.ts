import { test, expect, type Page } from './fixtures/offline';
import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

const root = resolve('../..');
const token = process.env.MED_TRANSCRIPT_TEST_KEY ||
  JSON.parse(readFileSync(resolve(root, 'data/local-config.json'), 'utf8')).access_key;
const fixture = resolve(root, 'data/browser-fixtures/dictation-timing.wav');
mkdirSync(resolve(root, 'data/browser-fixtures'), { recursive: true });
const source = readFileSync(resolve(
  root,
  'evaluation/datasets/primock57-smoke-v1/day1_consultation01_patient.utterance03.wav',
));
const datasetManifest = JSON.parse(readFileSync(
  resolve(root, 'evaluation/datasets/primock57-smoke-v1/manifest.json'), 'utf8',
));
const sourceSample = datasetManifest.samples.find((sample: { sample_id: string }) =>
  sample.sample_id === 'day1_consultation01_patient.utterance03',
);
const padded = Buffer.concat([source, Buffer.alloc(16000 * 2 * 3)]);
padded.writeUInt32LE(padded.length - 8, 4);
padded.writeUInt32LE(padded.length - 44, 40);
writeFileSync(fixture, padded);

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

test('measure synthetic draft latency and retain the critical approval block', async ({ page }, testInfo) => {
  test.setTimeout(180000);
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await createEncounter(page);
  await page.getByLabel('I am dictating synthetic test speech, and recording and local-processing authorization is documented.').check();
  await page.getByRole('button', { name: 'Start dictation', exact: true }).click();
  await expect(page.getByText('Recording · microphone is on', { exact: true })).toBeVisible();
  await page.waitForTimeout(9000);
  const recordStopAt = Date.now();
  await page.getByRole('button', { name: 'Stop & transcribe', exact: true }).click();
  await expect(page.getByLabel('Transcript segment 1')).toBeVisible({ timeout: 120000 });
  await expect(page.getByLabel('Transcript segment 1')).toHaveValue(/vomit/i);

  await page.getByLabel('Speaker role 1').selectOption('patient');
  await expect(page.getByLabel('Speaker role 1')).toHaveValue('patient');

  await page.getByLabel('I confirmed supported English.').check();
  await page.getByLabel('I reviewed source completeness.').check();
  await page.getByLabel('Review basis').fill('Reviewed the complete scripted synthetic recording.');
  await page.getByLabel('Correction reason').fill('No source corrections; confirm the scripted transcript for this timing run.');
  await page.getByRole('button', { name: 'Save source review', exact: true }).click();
  await expect(page.locator('.notice')).toContainText('Saved as a new source version');
  await page.getByRole('button', { name: 'Prepare facts', exact: false }).click();
  const cards = page.locator('.fact-card');
  await expect(cards.first()).toBeVisible();
  const count = await cards.count();
  for (let index = 0; index < count; index++) {
    const card = cards.nth(index);
    await card.getByRole('combobox', { name: 'Subject', exact: true }).selectOption('patient');
    await card.getByRole('combobox', { name: 'Temporality', exact: true }).selectOption('current');
    await card.getByLabel('Content and attribution reviewed').check();
    await card.getByLabel('Critical details checked').check();
  }
  await page.getByRole('button', { name: 'Save & verify note', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'SOAP preview' })).toBeVisible();
  const draftReadyAt = Date.now();
  const recordStopToDraftReadyMs = draftReadyAt - recordStopAt;

  const correctionCard = cards.first();
  const noteField = correctionCard.getByLabel('Note statement');
  const before = await noteField.inputValue();
  const correction = before.endsWith('.') ? before.slice(0, -1) : `${before}.`;
  await noteField.fill(correction);
  await correctionCard.getByLabel('Clinical clarification / exclusion reason').fill(
    'Synthetic punctuation-only correction; clinical meaning is unchanged.',
  );
  for (let index = 0; index < count; index++) {
    const card = cards.nth(index);
    await card.getByRole('combobox', { name: 'Subject', exact: true }).selectOption('patient');
    await card.getByRole('combobox', { name: 'Temporality', exact: true }).selectOption('current');
    await card.getByLabel('Content and attribution reviewed').check();
    await card.getByLabel('Critical details checked').check();
  }
  await page.getByRole('button', { name: 'Save & verify note', exact: true }).click();
  await expect(page.getByText('Saved a new note version and verification report.')).toBeVisible();
  const correctedNoteSavedAt = Date.now();
  await page.getByLabel('I rechecked the patient identifiers and the exact saved note.').check();
  const approve = page.getByRole('button', { name: 'Approve saved version', exact: false });
  await expect(page.locator('.review-side')).toContainText('structured field disagreement');
  await expect(approve).toBeDisabled();
  const metrics = {
    schema_version: 'synthetic_encounter_latency_metrics_v1',
    source_profile: 'local_scripted_non_asr_v1',
    dataset_id: datasetManifest.dataset_id,
    source_sample_id: sourceSample.sample_id,
    source_audio_sha256: sourceSample.audio_sha256,
    captured_fixture_sha256: createHash('sha256').update(padded).digest('hex'),
    task_completed: false,
    workflow_status: 'blocked_by_critical_verification',
    approval_issued: false,
    recording_stop_to_draft_ready_ms: recordStopToDraftReadyMs,
    correction_saved_to_blocked_verification_ms: Date.now() - correctedNoteSavedAt,
    export_ready_ms: null,
    transcript_fact_count: count,
    export_filename: null,
    export_status: null,
    export_sha256: null,
    interaction_errors: errors,
    human_observations: 0,
    clinical_accuracy_measured: false,
    clinical_acceptance: false,
  };
  const serialized = `${JSON.stringify(metrics, null, 2)}\n`;
  await testInfo.attach('synthetic-encounter-latency-metrics.json', {
    body: serialized, contentType: 'application/json',
  });
  const output = process.env.MTA_TIMING_OUTPUT;
  if (output) {
    mkdirSync(resolve(output, '..'), { recursive: true });
    writeFileSync(output, serialized, 'utf8');
  }
  console.log(`MTA_SYNTHETIC_TIMINGS ${JSON.stringify(metrics)}`);
  expect(metrics.task_completed).toBe(false);
  expect(metrics.workflow_status).toBe('blocked_by_critical_verification');
  expect(metrics.approval_issued).toBe(false);
  expect(metrics.recording_stop_to_draft_ready_ms).toBeGreaterThanOrEqual(0);
  expect(metrics.correction_saved_to_blocked_verification_ms).toBeGreaterThanOrEqual(0);
  expect(metrics.export_ready_ms).toBeNull();
  expect(errors).toEqual([]);
});
